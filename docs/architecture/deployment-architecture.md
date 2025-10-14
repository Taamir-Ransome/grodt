# Deployment Architecture
The application is fully containerized using Docker and orchestrated with Docker Compose for local deployment and testing. This ensures a consistent and reproducible environment.

Code snippet

graph TD
    subgraph "Docker Host"
        subgraph "Docker Network"
            A[Trading Bot App]
            B[Prometheus]
            C[Grafana]
        end
        D[(SQLite DB Volume)]

        A -- Python App --> D
        A -- /metrics endpoint --> B
        B -- Prometheus Query --> C
    end

    style A fill:#99CCFF
    style B fill:#FFCC99
    style C fill:#99FF99
Trading Bot App: The main Python application container running all core services (data, strategy, execution).

Prometheus: A time-series database container that scrapes the /metrics endpoint exposed by the Trading Bot App.

Grafana: A visualization platform container that connects to Prometheus as a data source to display real-time performance dashboards.

SQLite DB Volume: A persistent Docker volume is used to store the SQLite database file, ensuring that trade history and other data survive container restarts.
