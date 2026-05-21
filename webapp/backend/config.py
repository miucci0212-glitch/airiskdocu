import os
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: str = ""
    gemini_generation_model: str = "gemini-2.5-pro"
    gemini_fast_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "text-embedding-004"
    chroma_persist_dir: str = "./data/risk_db"
    krc_chroma_persist_dir: str = "./data/krc_db"
    source_xlsx_path: str = "./data/source/risk_db.xlsx"
    krc_source_xlsx_path: str = "./data/source/krc_risk_db.xlsx"
    krc_collection_name: str = "krc_db"
    template_xlsx_path: str = "./template/위험성평가서_template.xlsx"
    cell_map_path: str = "./template/cell_map.yaml"
    llm_timeout_sec: int = 60
    rate_limit_per_min: int = 10
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def make_paths_absolute(self) -> "Settings":
        base_dir = os.path.dirname(os.path.abspath(__file__))

        def resolve(path: str) -> str:
            if not os.path.isabs(path):
                return os.path.abspath(os.path.join(base_dir, path))
            return path

        self.chroma_persist_dir = resolve(self.chroma_persist_dir)
        self.krc_chroma_persist_dir = resolve(self.krc_chroma_persist_dir)
        self.source_xlsx_path = resolve(self.source_xlsx_path)
        self.krc_source_xlsx_path = resolve(self.krc_source_xlsx_path)
        self.template_xlsx_path = resolve(self.template_xlsx_path)
        self.cell_map_path = resolve(self.cell_map_path)
        return self


settings = Settings()
