from kafka import KafkaProducer
import json
import os

def load_kafka_brokers(path="path\\to\\EC2 instance material\\Pipeline\\0-config\\public_kafka_config.txt"):
    with open(path, "r") as f:
        for line in f:
            return line.strip()
    return None

def process_file(file_name):
    file_path = os.path.join(dir_path, file_name)
    print(f"Processing: {file_path}")
    sent_count = 0

    with open(file_path, 'r', encoding='utf-8') as events:
        for i, event in enumerate(events, 1):
            event = event.strip()
            if not event:
                continue

            try:
                json.loads(event)  # validazione JSON
                producer.send(topic="dma", value=event)
                sent_count += 1
            except json.JSONDecodeError as e:
                print(f"Errore di parsing al record {i}: {e}")
            except Exception as e:
                print(f"Errore generico nel file {file_name}, record {i}: {e}")

    print(f"Ho finito con {file_name}, inviati {sent_count} record.")

# Parametri per flessibilità: massimo numero di file da leggere
max_count = 1  # puoi cambiare questo numero
count = 0

# Cartella da cui leggere
dir_path = "path\\to\\dataset"

# Lista dei file ordinata alfabeticamente
files = sorted(os.listdir(dir_path))
if not files:
    raise FileNotFoundError("Nessun file trovato nella directory.")

# Carica broker Kafka
brokers = load_kafka_brokers()
if not brokers:
    raise ValueError("Kafka bootstrap servers not found in config file.")

# Inizializza un solo producer
producer = KafkaProducer(
    bootstrap_servers=brokers,
    value_serializer=lambda v: v.encode("utf-8")
)

# Processa i file, fermandosi al massimo impostato
for file_name in files:
    process_file(file_name)
    count += 1
    if count >= max_count:
        break

# Flush finale e chiusura
producer.flush()
producer.close()