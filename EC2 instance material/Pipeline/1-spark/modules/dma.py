from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

def dmaStream(spark, sf, brokers):
    dma_funcAggMap = {
        "value": [sf.avg, sf.max, sf.min]
    }
    
    # Costruisci lo schema degli id annidato
    string_col_names = "device_uuid component_uuid metric_id value"
      
    # Schema del JSON completo
    schema = StructType([
        StructField("metric", StructType([
            StructField("metric_id", StringType(), True),
            StructField("value", StructType([
                StructField("value", DoubleType(), True),
                StructField("timestamp", StructType([
                    StructField("seconds", DoubleType(), True)
                ]))
            ])),
            StructField("metric_metadata", StructType([
                StructField("device_uuid", StructType([
                    StructField("uuid", StringType(), True)
                ])),
                StructField("component_uuid", StructType([
                    StructField("uuid", StringType(), True)
                ]))
            ]))
        ]))
    ])

    # Lettura da Kafka
    df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", brokers) \
        .option("subscribe", "dma") \
        .option("startingOffsets", "latest") \
        .load()
        
    parsing_projections = []
    for name in string_col_names.split():
        if name in ["device_uuid", "component_uuid"]:
            parsing_projections.append(sf.col(f"data.metric.metric_metadata.{name}.uuid").alias(name))
        elif name == "value":
            parsing_projections.append(sf.col(f"data.metric.value.value").alias("value"))
        else:
            parsing_projections.append(sf.col(f"data.metric.{name}").alias(name))


    # Parsing del JSON
    # Dopo il parsing possiamo usare gli alias specificati anziché accedere alla colonna specificando data.field
    records = df.selectExpr("CAST(value AS STRING) AS json") \
        .select(sf.from_json(sf.col("json"), schema).alias("data")) \
        .select(
            sf.from_unixtime(sf.col("data.metric.value.timestamp.seconds")).cast("timestamp").alias("time_value"),
            *parsing_projections
        ) \
        .filter(sf.col("device_uuid").isNotNull() & sf.col("component_uuid").isNotNull())
        
    # escludiamo value per la proiezione prima della scrittura su kafka
    dma_col_names = [name for name in string_col_names.split() if name != "value"]
    aggregations = []
    for name, agg_funcs in dma_funcAggMap.items():
        for agg_func in agg_funcs:
            agg_name = f"{agg_func.__name__}_{name}"
            aggregations.append(agg_func(sf.col(name)).alias(f"{agg_func.__name__}_{name}"))
            dma_col_names.append(f"{agg_func.__name__}_{name}")
  
    # Aggregazione con finestra temporale 
    # Alcune colonne potrebbero contenere valori nulli, poi interpretati come NaN dopo la conversione in formato JSON 
    # Usiamo finestre di 5 minuti per evitare di avere troppe finestre
    windowed = records \
        .withWatermark("time_value", "1 minute") \
        .groupBy(sf.window(sf.col("time_value"), "3 minutes"), "device_uuid", "component_uuid", "metric_id") \
        .agg(*aggregations) \
        .select(
            sf.from_unixtime(
                (sf.unix_timestamp("window.start") + sf.unix_timestamp("window.end")) / 2
            ).alias("window_center"),
            *dma_col_names
        )
        
    query = windowed.select(
            sf.to_json(sf.struct(
                    sf.col("window_center"), # sf.col("window_center") è equivalente a "window_center"
                    *dma_col_names
                )
            ) \
            .alias("value")
        ) \
        .writeStream \
        .outputMode("append") \
        .format("kafka") \
        .option("kafka.bootstrap.servers", brokers) \
        .option("topic", "dma-out") \
        .option("truncate", False) \
        .option("checkpointLocation", "/dma/checkpoints") \
        .start()

    return query