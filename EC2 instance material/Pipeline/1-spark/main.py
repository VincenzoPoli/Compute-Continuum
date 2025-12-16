from pyspark.sql import SparkSession
from modules.containers import containersStream
from modules.machines import machinesStream
from modules.dma import dmaStream

import pyspark.sql.functions as sf

def load_kafka_brokers(path="/opt/spark/app/Pipeline/0-config/kafka_config.txt"):
    with open(path, "r") as f:
        for line in f:
            return line.strip()
    return None
    
if __name__ == "__main__":    
    brokers = load_kafka_brokers()
    if not brokers:
        raise ValueError("Kafka bootstrap servers not found in config file.")
    spark = SparkSession.builder.appName("StructuredStreaming").getOrCreate()
    dma_query = dmaStream(spark, sf, brokers)
    containers_query = containersStream(spark, sf, brokers)
    machines_query = machinesStream(spark, sf, brokers)
    dma_query.awaitTermination()
    containers_query.awaitTermination()
    machines_query.awaitTermination()
