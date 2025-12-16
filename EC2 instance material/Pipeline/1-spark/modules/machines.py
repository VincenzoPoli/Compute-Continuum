from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

def machinesStream(spark, sf, brokers):
    machine_funcAggMap = {

        # Machine Metrics
        "machine_cpu_cores": sf.avg,
        "machine_cpu_physical_cores": sf.avg,
        "machine_cpu_sockets": sf.avg,
        "machine_memory_bytes": sf.avg,
        "machine_nvm_avg_power_budget_watts": sf.last,
        "machine_nvm_capacity": sf.avg,
        "machine_scrape_error": sf.sum,
        "machine_swap_bytes": sf.avg,
    }

    ids_string_schema = "machine_id"

    # Costruisci lo schema delle metriche
    metrics_fields = [StructField(name, DoubleType(), True) for name in machine_funcAggMap.keys()]

    parsing_projections = [sf.col(f"data._source.metrics.{name}").alias(f"{name}") for name in machine_funcAggMap.keys()]
    for name in ids_string_schema.split():
        parsing_projections.append(sf.col(f"data._source.labels.{name}"))

    # Costruisci lo schema degli id
    ids_fields = [StructField(name, StringType(), True) for name in ids_string_schema.split()]

    # Schema del JSON
    # ogni record ha come campi: _index, _id, e _source
    # a noi interessa solo _source
    # a propria volta _source ha altri campi, di interesse sono solo @timestamp e metrics
    schema = StructType([
        StructField("_source", StructType([
            StructField("@timestamp", TimestampType()),
            StructField("metrics", StructType(metrics_fields)),
            StructField("labels", StructType(ids_fields))
        ]))
    ])

    # Lettura da Kafka
    df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", brokers) \
        .option("subscribe", "monitoring") \
        .option("startingOffsets", "latest") \
        .load()

    # Parsing del JSON
    # Dopo il parsing possiamo usare gli alias specificati anziché accedere alla colonna specificando data.field
    records = df.selectExpr("CAST(value AS STRING) AS json") \
        .select(sf.from_json(sf.col("json"), schema).alias("data")) \
        .select(
            sf.col("data._source.@timestamp").alias("time_value"),
            *parsing_projections
        ) \
        .filter(sf.col("machine_id").isNotNull())
        
    machine_aggr_funcs = [] # lista di funzioni di aggregazioni per metrica da fornire unpacked (.agg(*machine_aggr_funcs))
    machine_col_names = [] # lista delle colonne (funzione aggregata + nome metrica) per le proiezioni future, da fornire unpacked
    for name, agg_func in machine_funcAggMap.items():
        machine_aggr_funcs.append(agg_func(sf.col(name)).alias(f"{agg_func.__name__}_{name}"))
        machine_col_names.append(f"{agg_func.__name__}_{name}")
        
    # Aggregazione con finestra temporale 
    # Alcune colonne potrebbero contenere valori nulli, poi interpretati come NaN dopo la conversione in formato JSON 
    windowed = records \
        .withWatermark("time_value", "20 seconds") \
        .groupBy(sf.window(sf.col("time_value"), "1 minute"), "machine_id") \
        .agg(
            *machine_aggr_funcs
        ) \
        .select(
            sf.from_unixtime(
                (sf.unix_timestamp("window.start") + sf.unix_timestamp("window.end")) / 2
            ).alias("window_center"),
            "machine_id",
            *machine_col_names
        )
        
    query = windowed.select(
            sf.to_json(sf.struct(
                    sf.col("window_center"), # sf.col("window_center") è equivalente a "window_center"
                    "machine_id",
                    *machine_col_names
                )
            ) \
            .alias("value")
        ) \
        .writeStream \
        .outputMode("append") \
        .format("kafka") \
        .option("kafka.bootstrap.servers", brokers) \
        .option("topic", "machine-out") \
        .option("truncate", False) \
        .option("checkpointLocation", "/machine/checkpoints") \
        .start()

    return query