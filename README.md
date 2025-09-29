# Backend

## Technology

- **FastApi**
- **UV**
- **Podman**
    
    - To start podman: podman machine start

    - To build: podman build -t cetaceans-db .

    - To start container for the first time: podman run --name cetaceans-db -p 5432:5432 -d cetaceans-db

    - To start container after "podman run": podman start cetaceans-db

    - To stop container: podman stop cetaceans-db

    - To get into the db with the container started: podman exec -it cetaceans-db psql -U admin -d cetaceans

    