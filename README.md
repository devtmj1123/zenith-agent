# Todo List REST API

A RESTful API for managing todo items built with FastAPI and SQLite.

## Features

- Create new todos
- List all todos with filtering
- Get a specific todo
- Update todo details
- Delete todos
- Toggle completion status

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python main.py
   ```

3. Access the API documentation:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/todos` | Create a new todo |
| GET | `/todos` | List all todos |
| GET | `/todos/{id}` | Get a specific todo |
| PUT | `/todos/{id}` | Update a todo |
| DELETE | `/todos/{id}` | Delete a todo |
| PATCH | `/todos/{id}/complete` | Toggle completion status |

## Example Usage

### Create a Todo
```bash
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Learn FastAPI", "description": "Build a todo API"}'
```

### List All Todos
```bash
curl http://localhost:8000/todos
```

### List Completed Todos Only
```bash
curl "http://localhost:8000/todos?completed=true"
```

### Update a Todo
```bash
curl -X PUT http://localhost:8000/todos/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title", "completed": true}'
```

### Delete a Todo
```bash
curl -X DELETE http://localhost:8000/todos/1
```

## Data Models

### Todo Response
```json
{
  "id": 1,
  "title": "Learn FastAPI",
  "description": "Build a todo API",
  "completed": false,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```
