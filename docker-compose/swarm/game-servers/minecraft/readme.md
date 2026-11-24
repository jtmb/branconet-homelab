#MINECRAFT CONTAINER

<h1>RUN RCON CMD IN SWARM:</h1>
<!-- this will grab running container in swarm using your service name "gamesrv_minecraft-paper" regardless of container hash value -->
    docker exec -i $(docker ps --format '{{.Names}}' | grep gamesrv_minecraft-paper) rcon-cli