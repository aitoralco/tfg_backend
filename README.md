# Backend

## Technology

### FastApi

### UV

### Podman
    
💾 For the database a container with posgressSql is being used.

#### To start podman: 
```bash 
podman machine start 
```

#### To build: 
```bash 
podman build -t cetaceans-db .
```

#### To start container for the first time: 
```bash 
podman run --name cetaceans-db -p 5432:5432 -d cetaceans-db 
```

#### To start container after "podman run": 
```bash 
podman start cetaceans-db 
```

#### To stop container: 
```bash 
podman stop cetaceans-db 
```

#### To get into the db with the container started: 
```bash 
podman exec -it cetaceans-db psql -U admin -d cetaceans 
```

### For the backend

#### To start the backend

#### Get into WSL
```bash
conda create -n tfg-backend python=3.12 -y 
```

#### Then activate the virtual env and start the backend
```bash
conda activate tfg-backend
uv pip install -r requirements.txt
uvicorn main:app --reload --port 3000
```