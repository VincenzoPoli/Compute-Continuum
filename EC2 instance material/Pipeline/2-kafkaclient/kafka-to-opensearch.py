from kafka import KafkaConsumer
import json
from opensearchpy import OpenSearch
from dotenv import load_dotenv
import os

def load_opensearch_instances(path="/home/ec2-user/EC2 instance material/Pipeline/0-config/opensearch_config.txt"):
    with open(path, "r") as f:
        for line in f:
            return line.strip()
    return None

def load_kafka_brokers(path="/home/ec2-user/EC2 instance material/Pipeline/0-config/kafka_config.txt"):
    with open(path, "r") as f:
        for line in f:
            return line.strip()
    return None
    
if __name__ == "__main__":    
    
    instances = load_opensearch_instances();
    if not instances:
        raise ValueError("OpenSearch hosts not found in config file.")
    brokers = load_kafka_brokers();
    if not brokers:
        raise ValueError("Kafka bootstrap servers not found in config file.")
    
    load_dotenv()
    auth = ('admin', os.getenv('OPENSEARCH_PASSWORD'))

    client = OpenSearch(
        hosts=[{'host': ip.split(":")[0], 'port': int(ip.split(":")[1])} for ip in instances.split(",")],
        http_compress=True,
        http_auth=auth,
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False
    )

    patterns = {
        "container-out": "container", 
        "machine-out": "machine", 
        "dma-out": "dma"
    }

    ids = {
        "container": 0, 
        "machine": 0, 
        "dma": 0
    }

    mappings = { 
        "container": { 
            "mappings": {
                "properties": {
                    "window_center": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd HH:mm:ss"
                    },

                    "container_cpu_usage_seconds_total": { "type": "double" },
                    "container_cpu_system_seconds_total": { "type": "double" },
                    "container_cpu_user_seconds_total": { "type": "double" },
                    "container_cpu_load_average_10s": { "type": "double" },

                    "container_memory_usage_bytes": { "type": "long" },
                    "container_memory_max_usage_bytes": { "type": "long" },
                    "container_memory_rss": { "type": "long" },
                    "container_memory_working_set_bytes": { "type": "long" },
                    "container_memory_cache": { "type": "long" },
                    "container_memory_failcnt": { "type": "long" },
                    "container_memory_failures_total": { "type": "long" },
                    "container_memory_kernel_usage": { "type": "long" },
                    "container_memory_mapped_file": { "type": "long" },
                    "container_memory_swap": { "type": "long" },

                    "container_file_descriptors": { "type": "long" },
                    "container_fs_inodes_free": { "type": "long" },
                    "container_fs_inodes_total": { "type": "long" },
                    "container_fs_io_current": { "type": "long" },
                    "container_fs_io_time_seconds_total": { "type": "double" },
                    "container_fs_io_time_weighted_seconds_total": { "type": "double" },
                    "container_fs_limit_bytes": { "type": "long" },
                    "container_fs_read_seconds_total": { "type": "double" },
                    "container_fs_reads_bytes_total": { "type": "long" },
                    "container_fs_reads_merged_total": { "type": "long" },
                    "container_fs_reads_total": { "type": "long" },
                    "container_fs_sector_reads_total": { "type": "long" },
                    "container_fs_sector_writes_total": { "type": "long" },
                    "container_fs_usage_bytes": { "type": "long" },
                    "container_fs_write_seconds_total": { "type": "double" },
                    "container_fs_writes_bytes_total": { "type": "long" },
                    "container_fs_writes_merged_total": { "type": "long" },
                    "container_fs_writes_total": { "type": "long" },

                    "container_network_receive_bytes_total": { "type": "long" },
                    "container_network_receive_errors_total": { "type": "long" },
                    "container_network_receive_packets_dropped_total": { "type": "long" },
                    "container_network_receive_packets_total": { "type": "long" },
                    "container_network_transmit_bytes_total": { "type": "long" },
                    "container_network_transmit_errors_total": { "type": "long" },
                    "container_network_transmit_packets_dropped_total": { "type": "long" },
                    "container_network_transmit_packets_total": { "type": "long" },

                    "container_oom_events_total": { "type": "long" },
                    "container_processes": { "type": "integer" },
                    "container_scrape_error": { "type": "integer" },
                    "container_sockets": { "type": "integer" },
                    "container_threads": { "type": "integer" },
                    "container_threads_max": { "type": "integer" },
                    "container_tasks_state": { "type": "integer" },
                    "container_ulimits_soft": { "type": "integer" },

                    "container_spec_cpu_period": { "type": "long" },
                    "container_spec_cpu_shares": { "type": "long" },
                    "container_spec_memory_limit_bytes": { "type": "long" },
                    "container_spec_memory_reservation_limit_bytes": { "type": "long" },
                    "container_spec_memory_swap_limit_bytes": { "type": "long" },

                    "container_last_seen": { "type": "date" },
                    "container_start_time_seconds": { "type": "date" },

                    "container_blkio_device_usage_total": { "type": "long" }
                }
            }
        },
        "machine": {
            "mappings": {
                "properties": {
                    "window_center": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd HH:mm:ss"
                    },

                    "machine_cpu_cores": { "type": "integer" },
                    "machine_cpu_physical_cores": { "type": "integer" },
                    "machine_cpu_sockets": { "type": "integer" },
                    "machine_memory_bytes": { "type": "long" },
                    "machine_nvm_avg_power_budget_watts": { "type": "double" },
                    "machine_nvm_capacity": { "type": "long" },
                    "machine_scrape_error": { "type": "integer" },
                    "machine_swap_bytes": { "type": "long" }
                }
            }
        },
        "dma": {
            "mappings": {
                "properties": {
                    "window_center": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd HH:mm:ss"
                    },
                    "device_uuid": { "type": "keyword" },
                    "component_uuid": { "type": "keyword" },
                    "metric_id": { "type": "keyword" },
                    "type": { "type": "keyword" },
                    "status": { "type": "keyword" },
                    "avg_value": { "type": "double" },
                    "max_value": { "type": "double" },
                    "min_value": { "type": "double" }
                }
            }
        }
    }

    for topic, index_name in patterns.items():
        if not client.indices.exists(index=index_name):
            client.indices.create(index=index_name, body=mappings[index_name])

    topic_list = [name for name in patterns.keys()]

    consumer = KafkaConsumer(
        *topic_list,
        bootstrap_servers=brokers,
        auto_offset_reset='latest', # latest è l'opzione di default, ma l'ho specificata per ricordare che può essere cambiata
        enable_auto_commit=True, # Auto-commit offsets
    )

    try:
        for message in consumer:
            index_name = patterns[message.topic]
            ids[index_name] += 1
            document = json.loads(message.value)
            client.index(index=index_name, body=document, id=ids[index_name], refresh=True)

    except KeyboardInterrupt:
        print("KeyboardInterrupt...") # sarebbe più oppoertuno un sistema di logging dal momento che la pipeline sarà completamente containerizzata

    finally:
        consumer.close()
