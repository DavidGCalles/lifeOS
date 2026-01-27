import logging
from src.tools import TOOL_MAPPING

# ---------------------------------------------------------
# CONFIGURACIÓN: Lista de herramientas que requieren contexto
# ---------------------------------------------------------
CONTEXT_NEEDED = [
    "save_memory",
    "set_email",
    "calendar_list",
    "calendar_add",
    "calendar_remove"  # La nueva que acabamos de crear
]

logger = logging.getLogger(__name__)

def inject_runtime_context(current_user, tool_mapping=TOOL_MAPPING):
    """
    Itera sobre la lista de herramientas que requieren contexto
    e inyecta el usuario actual si la herramienta está activa.
    """
    injected_count = 0
    
    for tool_key in CONTEXT_NEEDED:
        tool_instance = tool_mapping.get(tool_key)
        
        if tool_instance:
            if hasattr(tool_instance, 'set_context'):
                tool_instance.set_context(current_user)
                injected_count += 1
            else:
                logger.warning(f"⚠️ Tool '{tool_key}' está en CONTEXT_NEEDED pero no tiene método .set_context()")
    
    logger.info(f"💉 Contexto inyectado en {injected_count} herramientas para: {current_user.name}")