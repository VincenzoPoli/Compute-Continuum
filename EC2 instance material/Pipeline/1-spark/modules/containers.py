from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

def containersStream(spark, sf, brokers):
    container_funcAggMap = {
        # CPU
        "container_cpu_usage_seconds_total": sf.last,
        "container_cpu_system_seconds_total": sf.last,
        "container_cpu_user_seconds_total": sf.last,
        "container_cpu_load_average_10s": sf.stddev,

        # Memory
        "container_memory_usage_bytes": sf.avg,
        "container_memory_max_usage_bytes": sf.max,
        "container_memory_rss": sf.avg,
        "container_memory_working_set_bytes": sf.avg,
        "container_memory_cache": sf.avg,
        "container_memory_failcnt": sf.max,
        "container_memory_failures_total": sf.last,
        "container_memory_kernel_usage": sf.avg,
        "container_memory_mapped_file": sf.avg,
        "container_memory_swap": sf.avg,

        # File ecc.
        "container_file_descriptors": sf.avg,
        "container_fs_inodes_free": sf.avg,
        "container_fs_inodes_total": sf.last,
        "container_fs_io_current": sf.avg,
        "container_fs_io_time_seconds_total": sf.last,
        "container_fs_io_time_weighted_seconds_total": sf.last,
        "container_fs_limit_bytes": sf.avg,
        "container_fs_read_seconds_total": sf.last,
        "container_fs_reads_bytes_total": sf.last,
        "container_fs_reads_merged_total": sf.last,
        "container_fs_reads_total": sf.last,
        "container_fs_sector_reads_total": sf.last,
        "container_fs_sector_writes_total": sf.last,
        "container_fs_usage_bytes": sf.avg,
        "container_fs_write_seconds_total": sf.last,
        "container_fs_writes_bytes_total": sf.last,
        "container_fs_writes_merged_total": sf.last,
        "container_fs_writes_total": sf.last,

        # Network
        "container_network_receive_bytes_total": sf.last,
        "container_network_receive_errors_total": sf.last,
        "container_network_receive_packets_dropped_total": sf.last,
        "container_network_receive_packets_total": sf.last,
        "container_network_transmit_bytes_total": sf.last,
        "container_network_transmit_errors_total": sf.last,
        "container_network_transmit_packets_dropped_total": sf.last,
        "container_network_transmit_packets_total": sf.last,

        # Events, Threads & Processes
        "container_oom_events_total": sf.last,
        "container_processes": sf.avg,
        "container_scrape_error": sf.sum,
        "container_sockets": sf.avg,
        "container_threads": sf.avg,
        "container_threads_max": sf.max,
        "container_tasks_state": sf.avg,
        "container_ulimits_soft": sf.avg,

        # Container Specs
        "container_spec_cpu_period": sf.avg,
        "container_spec_cpu_shares": sf.avg,
        "container_spec_memory_limit_bytes": sf.avg,
        "container_spec_memory_reservation_limit_bytes": sf.avg,
        "container_spec_memory_swap_limit_bytes": sf.avg,

        # Time & Metadata
        "container_last_seen": sf.max,
        "container_start_time_seconds": sf.min,

        # Device usage
        "container_blkio_device_usage_total": sf.last
    }

    ids_string_schema = "lau_serial instance"

    # Costruisci lo schema delle metriche
    metrics_fields = [StructField(name, DoubleType(), True) for name in container_funcAggMap.keys()]

    parsing_projections = [sf.col(f"data._source.metrics.{name}").alias(f"{name}") for name in container_funcAggMap.keys()]
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
        .filter(sf.col("lau_serial").isNotNull() & sf.col("instance").isNotNull())

    container_aggr_funcs = [] # lista di funzioni di aggregazioni per metrica da fornire unpacked (.agg(*container_aggr_funcs))
    container_col_names = [] # lista delle colonne (funzione aggregata + nome metrica) per le proiezioni future, da fornire unpacked
    for name, agg_func in container_funcAggMap.items():
        container_aggr_funcs.append(agg_func(sf.col(name)).alias(f"{agg_func.__name__}_{name}"))
        container_col_names.append(f"{agg_func.__name__}_{name}")
    
    # Aggregazione con finestra temporale 
    # Alcune colonne potrebbero contenere valori nulli, poi interpretati come NaN dopo la conversione in formato JSON 
    windowed = records \
        .withWatermark("time_value", "20 seconds") \
        .groupBy(sf.window(sf.col("time_value"), "1 minute"), "lau_serial", "instance") \
        .agg(
            *container_aggr_funcs
        ) \
        .select(
            sf.from_unixtime(
                (sf.unix_timestamp("window.start") + sf.unix_timestamp("window.end")) / 2
            ).alias("window_center"),
            "lau_serial", 
            "instance", 
            *container_col_names
        )
        
    # Scrittura su Kafka
    query = windowed.select(
            sf.to_json(sf.struct(
                    "window_center", # sf.col("window_center") è equivalente a "window_center"
                    "lau_serial",
                    "instance",
                    *container_col_names
                )
            ) \
            .alias("value")
        ) \
        .writeStream \
        .outputMode("append") \
        .format("kafka") \
        .option("kafka.bootstrap.servers", brokers) \
        .option("topic", "container-out") \
        .option("truncate", False) \
        .option("checkpointLocation", "/container/checkpoints") \
        .start()
        
    return query