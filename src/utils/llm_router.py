import os
import yaml
import logging
import litellm  # <--- IMPORTANTE: Importamos la librería base
from typing import Any
from litellm import Router

# Configuración de logs
logger = logging.getLogger(__name__)

class LiteLLMRouter:
    """
    Singleton Wrapper around litellm.Router.
    Allows in-process LLM usage using the same configuration as the Proxy container,
    eliminating network latency for the Fast Track.
    """
    _instance = None
    _router = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LiteLLMRouter, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """
        Loads litellm_config.yaml and initializes the internal Router.
        """
        # --- DESACTIVAR TELEMETRÍA "RUIDOSA" ---
        # Evita que litellm intente loguear métricas al salir, causando el error de atexit
        litellm.telemetry = False
        litellm.success_callback = []
        litellm.failure_callback = []
        # ---------------------------------------

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "litellm_config.yaml")

        if not os.path.exists(config_path):
            error_msg = f"❌ LiteLLMRouter: Config file not found at {config_path}"
            logger.critical(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            model_list = config.get("model_list", [])
            router_settings = config.get("router_settings", {})

            fallbacks = router_settings.get("fallbacks", [])
            allowed_fails = router_settings.get("allowed_fails", 3)
            cooldown_time = router_settings.get("cooldown_time", 1)

            logger.info(f"⚡ Initializing Embedded LiteLLM Router with {len(model_list)} models.")
            
            self._router = Router(
                model_list=model_list,
                fallbacks=fallbacks,
                allowed_fails=allowed_fails,
                cooldown_time=cooldown_time,
                set_verbose=False 
            )
            
        except Exception as e:
            logger.critical(f"❌ Failed to initialize LiteLLMRouter: {e}", exc_info=True)
            raise e

    async def acompletion(self, **kwargs) -> Any:
        if not self._router:
            raise RuntimeError("LiteLLMRouter not initialized.")
        return await self._router.acompletion(**kwargs)