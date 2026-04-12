import uvicorn
import sys
import os
from modules.config_loader import get_config

if __name__ == "__main__":
    # Use the import string format to support 'reload=True'
    app_import_string = "modules.api.api:app"

    # Replicate original parameter logic
    config = get_config()
    port = config["server"]["port"]
    log_level = os.environ.get("INGEST_LOG_LEVEL", "debug").lower()

    print(f"🚀 Starting Ingest API on port {port} (log_level: {log_level})...")

    try:
        uvicorn.run(
            app_import_string, 
            host="0.0.0.0", 
            port=port, 
            log_level=log_level, 
            reload=True
        )
    except Exception as e:
        print(f"❌ Failed to start API: {e}")
        sys.exit(1)