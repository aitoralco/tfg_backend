# Backend

## Technology

### FastApi

### UV

### Podman
    
*To start podman*: 
    ```bash 
        podman machine start 
    ```

    - To build: ```bash podman build -t cetaceans-db ```

    - To start container for the first time: ```bash podman run --name cetaceans-db -p 5432:5432 -d cetaceans-db ```

    - To start container after "podman run": ```bash podman start cetaceans-db ```

    - To stop container: ```bash podman stop cetaceans-db ```

    - To get into the db with the container started: ```bash podman exec -it cetaceans-db psql -U admin -d cetaceans ```

