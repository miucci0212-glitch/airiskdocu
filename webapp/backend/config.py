from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: str = ""
    gemini_generation_model: str = "gemini-2.5-pro"
    gemini_fast_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "text-embedding-004"
    chroma_persist_dir: str = "./data/risk_db"
    source_xlsx_path: str = "./data/source/risk_db.xlsx"
    krc_source_xlsx_path: str = "./data/source/krc_risk_db.xlsx"
    krc_collection_name: str = "krc_db"
    template_xlsx_path: str = "./template/위험성평가서_template.xlsx"
    cell_map_path: str = "./template/cell_map.yaml"
    llm_timeout_sec: int = 60
    rate_limit_per_min: int = 10
    allowed_origins: str = "http://localhost:3000"
    log_level: str = "INFO"


settings = Settings()
