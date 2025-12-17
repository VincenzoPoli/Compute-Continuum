# Avvio Soluzione di Acquisizione ed Elaborazione dati su AWS (usando ParallelCluster e altri strumenti a supporto)

## Nota 1
Quanto di seguito presuppone la conoscenza dei concetti di base relativi ai Web Services offerti da Amazon (configurazione elementare ruoli IAM, security group, generazione chiavi) oltre al possesso di un account con un numero di crediti sufficiente.

Verranno quindi riportate solo le istruzioni atte ad avviare quanto presente nella repository in un proprio ambiente già correttamente configurato.

## Nota 2

Nella repository sono presenti dei file che rappresenta un array di record JSON. Questi sono SOLO esempi di dati utilizzati per la realizzazione (e il test) della soluzione. 

I dataset originari contengono decine e decine di file con all'interno centinaia di migliaia di record per un totale di svariati GB. Dal momento che GitHub non è un datacenter, ci si è limitati a fornire dei campioni.

kafkaRTSim e i dataset NON vanno caricati sul cluster che si intende usato. Queste componenti sono deputate alla simulazione dell'arrivo di eventi/dati, e devono essere localizzati su una (o più) macchina esterna al cluster.

## Un po' di contesto

[Presentazione Google Slides](https://docs.google.com/presentation/d/1E0KLCN3N69sAchmcqAzFqAeN7ytEOoZseU2YUqSRaQQ/edit?usp=sharing)

[Abstract (in italiano)](https://drive.google.com/file/d/1uU_ecifNT-EklnCg7eSU_jDsmzxn2UxU/view?usp=sharing)

[Abstract (in english)](https://drive.google.com/file/d/1q2Dq6H74nyMJGNKUT7amyaDScHxNA0QN/view?usp=sharing)

## Prerequisiti

Creazione ambiente virtuale Python

```
python -m virtualenv ~/parallel-cluster
```

Attivazione ambiente virtuale

```
virtualenv attivazione: path\to\~\parallel-cluster\Scripts\activate.bat
```

Installare nvm e Node.js LTS:  

```
nvm install lts 
```

```
nvm use lts
```

Installare AWS CLI: 

```
pip install awscli
```

Configurare AWS CLI

```
aws configure
```

Configurare il cluster

```
pcluster configure --config cluster-config.yaml
```

Il file creato si troverà sotto la directory di lavoro corrente. Nella repo è già disponibile un manifesto d'esempio utilizzabile.

## Creazione ed eliminazione cluster

Aprire il terminale Windows e lanciare:

```
path\to\your\venv\parallelcluster\activate.bat
```

Posizionarsi sotto la directory in cui è presente il manifest "cluster-config.yaml" che contiene le informazioni per la creazione del cluster:

```
cd "path\to\cluser-config.yaml"
```

Avviare la creazione:

```
pcluster create-cluster --cluster-name test-cluster --cluster-configuration cluster-config.yaml
```

Per avviare la distruzione:

```
pcluster delete-cluster --region eu-south-1 --cluster-name test-cluster
```

## Gestione connessione al cluster

Posizionarsi sotto la directory dove è presente la coppia di chiavi. Nella repository è presente un file denominato **your-key-pair.pem.txt** che fa da placeholder per quella associata al proprio cluster:

```
cd "path\to\EC2 instance material\Key"
```

Avviare la connessione lanciando:

```
pcluster ssh --cluster-name test-cluster -i milan-key-pair.pem
```

Per chiudere la connessione:

```
exit
```

## Gestione nodi e preparazione ambiente

Avviata la connessione, aprire una sessione di terminale sull'head node.

Allocare i compute node (e.g. 7 per 2 ore):

```
salloc -N7 --exclusive --time=02:00:00
```

### Copiare materiale sull'head node

Aprire un terminale Windows e posizionarsi sotto la directory dove è presente la coppia di chiavi:

```
cd "path\to\EC2 instance material\Key"
```

Lanciare: 

```
scp -r -i milan-key-pair.pem "path\to\EC2 instance material" ec2-user@<public-head-node-ip>:~/
```

L'ip pubblico dell'head node è facilmente reperibile dalla console AWS: è sufficiente accedere alla sezione EC2 instance e visualizzare le istanze in esecuzione.

### Assegnazione ruolo ad ogni compute node

E' necessario assegnare i ruoli per ogni compute node. Questo consentirà la possibilità di lanciare script di configurazione dinamica degli ambienti Kafka, Spark e Opensearch e tenere traccia di quale nodo è deputato a fare cosa.

Per ottenere i nodi allocati uno per riga, senza duplicati:

```
#
# ${nodes[@]} → restituisce il valore
# ${!nodes[@]} → restituisce la chiave (stringa o indice numerico)
#

nodes=($(srun hostname | sort -u))
```

Assegnazione ruoli:

```
#
# Definizione numero di nodi per piattaforma
#

n_kafka=2
n_spark=5

kafka_nodes=""
spark_workers=""
opensearch_nodes=""

for i in "${!nodes[@]}"; do
    host="${nodes[$i]}"
    if (( i < n_kafka )); then
        kafka_nodes+="$host,"
    elif (( i < n_spark + n_kafka )); then
        if (( i == n_kafka )); then
            SPARK_MASTER="$host"
        else
            spark_workers+="$host,"
        fi
    else
        opensearch_nodes+="$host,"
    fi
done

# Rimozione dell'ultima virgola
KAFKA_NODES="${kafka_nodes%,}"
SPARK_WORKERS="${spark_workers%,}"
OPENSEARCH_NODES="${opensearch_nodes%,}"

# Esportazione variabili di ambiente in un file usando here document
cat <<EOF > cluster_env.sh
export KAFKA_NODES="$KAFKA_NODES"
export SPARK_MASTER="$SPARK_MASTER"
export SPARK_WORKERS="$SPARK_WORKERS"
export OPENSEARCH_NODES="$OPENSEARCH_NODES"
EOF
```

Per importare le variabili di ambiente scritte nell'here document (utile se per qualche ragione non abbiamo più accesso ad alcune variabili)

```
source cluster_env.sh
```

Creare due config file (uno relativo a Kafka e l'altro ad Opensearch) che saranno usati dagli snippet Python (Spark ecc.) per interagire coi nodi e gli ambienti Kafka e Opensearch.

Spostarsi sotto 0-config:

```
cd 'EC2 instance material/Pipeline/0-config/'
```

Lanciare lo script:

```
# Kafka: costruzione lista IP:porta
kafka_ips=""
for host in ${KAFKA_NODES//,/ }; do
	ip=$(getent hosts "$host" | awk '{print $1}')
    kafka_ips+="$ip:9092,"
done
kafka_ips="${kafka_ips%,}"  # rimuove l'ultima virgola
echo "$kafka_ips" > kafka_config.txt

# OpenSearch: costruzione lista IP:porta
search_ips=""
for host in ${OPENSEARCH_NODES//,/ }; do
	ip=$(getent hosts "$host" | awk '{print $1}')
    search_ips+="$ip:9200,"
done
search_ips="${search_ips%,}"
echo "$search_ips" > opensearch_config.txt
```

### Installazione e avvio Docker 

Prima di tutto, dal momento che abbiamo risorse limitate, dobbiamo minimizzare le possibilità di node failure, in particolare quelli legati alla memoria. Per farlo, ogni nodo dovrà gestire uno swapfile di 2G.

Gestione swapfile head node:

```
set -e

# 1. Crea il file di swap (solo se non esiste)
if [ ! -f /swapfile ]; then
    if command -v fallocate &> /dev/null; then
        sudo fallocate -l 2G /swapfile || echo "fallocate fallito, provo con dd..."
    fi
    # Se fallocate ha fallito o non esiste, usa dd
    if [ ! -s /swapfile ]; then
        sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    fi
fi

# 2. Imposta i permessi
sudo chmod 600 /swapfile

# 3. Inizializza lo swap (solo se non già inizializzato)
if ! sudo swapon --show | grep -q "/swapfile"; then
    sudo mkswap /swapfile
    sudo swapon /swapfile
fi

# 4. Rendi lo swap permanente (solo se non già presente)
if ! grep -q "^/swapfile" /etc/fstab; then
    echo "/swapfile swap swap defaults 0 0" | sudo tee -a /etc/fstab
fi
```

Gestione swapfile compute node:

```
nodes=($(srun hostname | sort -u))

for host in "${nodes[@]}"; do
	srun --nodelist="$host" --ntasks=1 bash -c '
            set -e

            # 1. Crea il file di swap (solo se non esiste)
            if [ ! -f /swapfile ]; then
                if command -v fallocate &> /dev/null; then
                    sudo fallocate -l 2G /swapfile || echo "fallocate fallito, provo con dd..."
                fi
                # Se fallocate ha fallito o non esiste, usa dd
                if [ ! -s /swapfile ]; then
                    sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
                fi
            fi

            # 2. Imposta i permessi
            sudo chmod 600 /swapfile

            # 3. Inizializza lo swap (solo se non già inizializzato)
            if ! sudo swapon --show | grep -q "/swapfile"; then
                sudo mkswap /swapfile
                sudo swapon /swapfile
            fi

            # 4. Rendi lo swap permanente (solo se non già presente)
            if ! grep -q "^/swapfile" /etc/fstab; then
                echo "/swapfile swap swap defaults 0 0" | sudo tee -a /etc/fstab
            fi
            ' &
done
wait
```

Installare e avviare Docker sull'head node:

```
sudo yum install docker -y
sudo systemctl start docker 
```

Installare e avviare docker su tutti i compute node:

```
nodes=($(srun hostname | sort -u))

for host in "${nodes[@]}"; do
    srun --nodelist="$host" sudo yum install docker -y &
done
wait

for host in "${nodes[@]}"; do
    srun --nodelist="$host" sudo systemctl start docker &
done
wait
```

### Installazione e avvio ambiente Kafka

Per avere più broker Kafka tra loro coordinati, è necessario avviare più istanze Kafka avendo però l'accortezza di registrare opportunamente listener e quorum voters, azione che è possibile fare solo dopo aver designato quali nodi avranno il ruolo di listener e controller.

Questo procedimento si baserà sui ruoli definiti inizialmente.

Creazione quorum voter:

```
#
# Costruzione del quorum controller
# pattern da sostituire definito con //
# pattern che sostiuisce definito da /
# quindi sostituiamo le virgole (//,) con gli spazi (/ ), ottenendo una stringa iterabile
#
i=1
quorum=""

for host in ${KAFKA_NODES//,/ }; do
	ip=$(getent hosts "$host" | awk '{print $1}')
    quorum+="${i}@${ip}:9093,"
    ((i++))
done

quorum="${quorum%,}"
```

Generazione cluster ID (va generato una sola volta e dev'essere unico per il cluster e condiviso tra i nodi, attenzione quindi a non chiudere la shell)

```
KAFKA_CLUSTER_ID=$(uuidgen)
```

Non resta che avviare Kafka, registrato i quorum voter e i listener (registreremo sia listener che permettono interazioni interne alla rete usando gli ip privati, che esterne alla rete usando ip pubblici).

La configurazione usata non è adatta alla messa in produzione, infatti ogni nodo ha la doppia funzione (broker e controller). Tuttavia, usare troppe risorse per seguire le best practice potrebbe portare a node failer, oltre che toglierne a Opensearch e Spark. Questo compromesse permette di implementare un minimo di fault tolerance coerentemente con ciò che abbiamo a disposizione.

Avvio dei broker Kafka su ciascun Kafka compute node:

```
i=1
for host in ${KAFKA_NODES//,/ }; do
    id=$i
	ip=$(getent hosts "$host" | awk '{print $1}')
	public_ip=$(srun --nodelist="$host" --ntasks=1 --output=- curl -s ifconfig.me)
    srun --nodelist="$host" --ntasks=1 bash -c "
        sudo docker rm -f kafka-$id || true

        sudo mkdir -p /var/lib/kafka-$id
        sudo chown 1000:1000 /var/lib/kafka-$id

        sudo docker run -d --name kafka-$id \
            -p 9092:9092 \
            -p 9093:9093 \
            -p 9094:9094 \
            -e KAFKA_NODE_ID=$id \
            -e KAFKA_PROCESS_ROLES=broker,controller \
            -e KAFKA_CLUSTER_ID=$KAFKA_CLUSTER_ID \
            -e KAFKA_CONTROLLER_QUORUM_VOTERS='$quorum' \
            -e KAFKA_LISTENERS='INTERNAL://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093,EXTERNAL://0.0.0.0:9094' \
            -e KAFKA_ADVERTISED_LISTENERS='INTERNAL://$ip:9092,CONTROLLER://$ip:9093,EXTERNAL://$public_ip:9094' \
            -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP='INTERNAL:PLAINTEXT,CONTROLLER:PLAINTEXT,EXTERNAL:PLAINTEXT' \
            -e KAFKA_INTER_BROKER_LISTENER_NAME=INTERNAL \
            -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
            -e KAFKA_LOG_DIRS=/var/lib/kafka-$id \
            -e KAFKA_HEAP_OPTS='-Xmx256m -Xms128m' \
            -v /var/lib/kafka-$id:/var/lib/kafka-$id \
            apache/kafka:latest
    " &
    ((i++))
done
wait
```

Costruzione della stringa bootstrap-server con tutti gli IP dei broker Kafka

```
bootstrap=""
for host in ${KAFKA_NODES//,/ }; do
	ip=$(getent hosts "$host" | awk '{print $1}')
    bootstrap+="$ip:9092,"
done
bootstrap="${bootstrap%,}" 
```

Configurato correttamente il cluster Kafka, sarà sufficiente contattare un solo nodo per la creazione dei topic. Le opzioni usate e la configurazione al passo precedente faranno il resto: sarà Kafka a gestire opportunamente partizioni, repliche e node failure (fault tolerance)

Ottenere un qualsiasi nodo (e.g. il primo):

```
# %%,* elimina la più lunga (%%) sottostringa qualsiasi (*) a partire dalla virgola (,)
first_node="${KAFKA_NODES%%,*}"
```

Creazione topic:

```
IFS=',' read -ra nodes <<< "$KAFKA_NODES"
num_nodes="${#nodes[@]}"

srun --nodelist="$first_node" --ntasks=1 sudo docker exec kafka-1 bash -c "
	cd /opt/kafka &&
	bin/kafka-topics.sh --bootstrap-server $bootstrap --create --topic monitoring --replication-factor $num_nodes &&
	bin/kafka-topics.sh --bootstrap-server $bootstrap --create --topic dma --replication-factor $num_nodes &&
	bin/kafka-topics.sh --bootstrap-server $bootstrap --create --topic container-out --replication-factor $num_nodes &&
	bin/kafka-topics.sh --bootstrap-server $bootstrap --create --topic machine-out --replication-factor $num_nodes &&
	bin/kafka-topics.sh --bootstrap-server $bootstrap --create --topic dma-out --replication-factor $num_nodes
"
```

### Installazione e avvio Opensearch

Valorizzazione password: 

```
admin_pwd='la-tua-password'
```

**NB**: la password ha requisiti specifici. La documentazione che fornisce tali requisiti è reperibile facilmente.

Costruzione discovery.seed_hosts e cluster.initial_master_nodes:

```
seed_hosts=""
initial_masters=""

i=1
for host in ${OPENSEARCH_NODES//,/ }; do
	ip=$(getent hosts "$host" | awk '{print $1}')
    seed_hosts+="$ip,"
    initial_masters+="opensearch-$i,"
    ((i++))
done

seed_hosts="${seed_hosts%,}"
initial_masters="${initial_masters%,}"
```

Configurazione vm.max_map_count su ogni nodo Opensearch:

```
for host in ${OPENSEARCH_NODES//,/ }; do
    srun --nodelist="$host" --ntasks=1 bash -c "
        sudo sysctl -w vm.max_map_count=262144 &&
        echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
    " 
done
```

Avvio container Opensearch:

```
i=1
for host in ${OPENSEARCH_NODES//,/ }; do
    name="opensearch-$i"
	
    srun --nodelist="$host" --ntasks=1 bash -c "
        sudo docker rm -f '$name' || true
        sudo docker run -d --name '$name' \
            --network host \
            -e 'cluster.name=opensearch-cluster' \
            -e 'node.name=$name' \
            -e 'discovery.seed_hosts=$seed_hosts' \
            -e 'cluster.initial_cluster_manager_nodes=$initial_masters' \
            -e 'network.host=0.0.0.0' \
            -e 'OPENSEARCH_INITIAL_ADMIN_PASSWORD=$admin_pwd' \
            -e 'OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m -Dplugins.knn.circuit_breaker.triggered_limit=512mb' \
            opensearchproject/opensearch:3
    " &
    ((i++))
done
wait
```

Non resta che avviare Dashboards. Come per Kafka, è sufficiente contattare un nodo qualsiasi per avere accesso al cluster. 

Avvio Dashboards dall'head node:

```
first_opensearch_host="${OPENSEARCH_NODES%%,*}"

first_opensearch_ip=$(getent hosts "$first_opensearch_host" | awk '{print $1}')

sudo docker rm -f opensearch-dashboards || true

sudo docker run -d --name opensearch-dashboards \
    -p 5601:5601 \
    -e OPENSEARCH_HOSTS="[\"https://${first_opensearch_ip}:9200\"]" \
    -e OPENSEARCH_USERNAME="admin" \
    -e OPENSEARCH_PASSWORD="$admin_pwd" \
    -e OPENSEARCH_SSL_VERIFICATIONMODE="none" \
    opensearchproject/opensearch-dashboards:3
```

Per accedere a Dashboards dal proprio PC (e quindi mediante una connessione esterna), è necessario aggiungere un regola in entrata TCP personalizzata che abiliti almeno la connessione che ha come origine il proprio IP e come porta 5601. 

Per farlo, è basta selezionare l'istanza dell'head node e andare nella scheda 'sicurezza'. Cliccare su uno dei nomi gruppi e aggiungere suddetta regola.

Dalla console AWS è facile risalire all'ip pubblico dell'head node. Per accedere a Dashboards quindi:

```
http://<head-node-public-IP>:5601
```

### Installazione e avvio Spark

Affinché Spark possa lavorare con gli snippet python senza incorrere in problemi, è necessario fornire i permessi alla directory (e al suo contenuto) che, nell'ambiente containerizzato spark, corrisponderà alla workdir "/opt/spark/app".
La directory in questione è "EC2 instance material"

Posizionarsi sotto EC2 instance material:

```
cd
cd 'EC2 instance material'
```

Assegnare i permessi a PWD e tutto il suo contenuto:

```
chmod -R 755 "$PWD"
```

Lanciare Spark prima sul master node e poi su tutti i worker node: 

```
srun --nodelist="$SPARK_MASTER" --ntasks=1 bash -c "
sudo mkdir -p /mnt/spark-checkpoints-1
sudo mkdir -p /mnt/spark-checkpoints-2
sudo mkdir -p /mnt/spark-checkpoints-3

sudo chown 1001:1001 /mnt/spark-checkpoints-1
sudo chown 1001:1001 /mnt/spark-checkpoints-2
sudo chown 1001:1001 /mnt/spark-checkpoints-3

sudo chmod 775 /mnt/spark-checkpoints-1
sudo chmod 775 /mnt/spark-checkpoints-2
sudo chmod 775 /mnt/spark-checkpoints-3

# Esporta in lettura e scrittura i volumi e riavvi nfs-server per rendere operativi le modifiche al file exports

echo \"/mnt/spark-checkpoints-1 *(rw)\" | sudo tee -a /etc/exports
echo \"/mnt/spark-checkpoints-2 *(rw)\" | sudo tee -a /etc/exports
echo \"/mnt/spark-checkpoints-3 *(rw)\" | sudo tee -a /etc/exports

sudo exportfs -a
sudo systemctl restart nfs-server

sudo docker rm -f spark-master || true
sudo docker run -d --name spark-master \
    --network host \
    -e SPARK_MODE=master \
    -e SPARK_MASTER_HOST=\"$SPARK_MASTER\" \
    -e SPARK_MASTER_PORT=7077 \
    -e SPARK_MASTER_WEBUI_PORT=8080 \
    -e HOME=/opt/spark/app \
    -e SPARK_DRIVER_MEMORY=1024m \
    -e SPARK_WORKER_MEMORY=1024m \
    -v \"$PWD:/opt/spark/app\" \
    -v /mnt/spark-checkpoints-1:/container/checkpoints \
    -v /mnt/spark-checkpoints-2:/machine/checkpoints \
    -v /mnt/spark-checkpoints-3:/dma/checkpoints \
    bitnamilegacy/spark:3.5.1
"
```

```
i=1
for host in ${SPARK_WORKERS//,/ }; do
    srun --nodelist="$host" --ntasks=1 bash -c "

    sudo mkdir -p /mnt/spark-checkpoints-1
    sudo mkdir -p /mnt/spark-checkpoints-2
    sudo mkdir -p /mnt/spark-checkpoints-3

    sudo mount $SPARK_MASTER:/mnt/spark-checkpoints-1 /mnt/spark-checkpoints-1
    sudo mount $SPARK_MASTER:/mnt/spark-checkpoints-2 /mnt/spark-checkpoints-2
    sudo mount $SPARK_MASTER:/mnt/spark-checkpoints-3 /mnt/spark-checkpoints-3

    sudo docker rm -f spark-worker-$i || true

    sudo docker run -d --name spark-worker-$i \
        --network host \
        -v /mnt/spark-checkpoints-1:/container/checkpoints \
        -v /mnt/spark-checkpoints-2:/machine/checkpoints \
        -v /mnt/spark-checkpoints-3:/dma/checkpoints \
        -e SPARK_MODE=worker \
        -e SPARK_MASTER_URL=spark://$SPARK_MASTER:7077 \
        -e SPARK_WORKER_MEMORY=1024m \
        -e SPARK_EXECUTOR_MEMORY=1024m \
        bitnamilegacy/spark:3.5.1
    " &
    ((i++))
done

wait
```
## Esecuzione Pipeline Spark-based

Installare requirements:

```
pip3 install kafka-python &
pip3 install opensearch-py &
pip3 install python-dotenv &
wait
```

### Avviare client Kafka to Opensearch 

Posizionarsi sotto la directory dove è presente lo snippet kafka-to-opensearch.py:

```
cd
cd 'EC2 instance material/Pipeline/2-kafkaclient'
```

Avviare il client in background:

```
python3 kafka-to-opensearch.py &
```

### Ricavare IP Spark Master e nodi Kafka per regole traffico in entrata, config file ecc.

- Ricavare l'IP del master Spark:

```
echo $(getent hosts "$SPARK_MASTER" | awk '{print $1}')
```

- Ricavare gli IP privati dei nodi Kafka lanciando:

```
for host in ${KAFKA_NODES//,/ }; do
    echo $(getent hosts "$host" | awk '{print $1}')
done
```

- Vedere la corrispondenza tra gli IP privati e quelli pubblici avvalendosi della console AWS

- Usare le corrispondenze per aggiungere regole di connessioni in entrata TCP personalizzate (porte 4040 e 9094)

### Avviare la Pipeline Spark

Posizionarsi sotto EC2 instance material:

```
cd
cd 'EC2 instance material'
```

Avviare main.py :

```
srun --nodelist="$SPARK_MASTER" --ntasks=1 bash -c '
    sudo docker exec spark-master \
    /opt/bitnami/spark/bin/spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
    --master spark://'"$SPARK_MASTER"':7077 \
    /opt/spark/app/Pipeline/1-spark/main.py
'

srun --nodelist="$SPARK_MASTER" --ntasks=1 bash -c '
    sudo docker exec spark-master \
    /opt/bitnami/spark/bin/spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
    --master spark://'"$SPARK_MASTER"':7077 \
    /opt/spark/app/Pipeline/1-spark/main.py || echo "[WARN] Spark failed, continuing anyway."
    exit 0
'

```

### Avviare simulatore eventi

- Vedere la corrispondenza tra gli IP privati e quelli pubblici avvalendosi della console AWS

- Sotto "path\to\kafkaRTSim\0-config", aprire il file "public_kafka_config.txt" e scrivere gli IP corredati dal numero di porta tutti su una riga nella seguente maniera:

```
<IP_PUBBLICO_1>:9094,<IP_PUBBLICO_2>:9094
```

- Aprire due terminali Windows e posizionarsi sotto la directory contenente i due snippet che simulano l'arrivo di eventi:

```
cd "path\to\kafkaRTsim"
```

- Per lanciarli:

```
start /B python stream-sim-1.py
start /B python stream-sim-2.py
```