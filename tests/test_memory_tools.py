"""Tests herméticos de la traducción de borde — v3-FR-02b (#169).

El objeto bajo test es la CAPA DE TRADUCCIÓN (persona → substrato), NO el
transporte: el cliente MCP va mockeado (AsyncMock), sin red y sin coreAI
corriendo. El contrato del substrato contra el que se traduce es público
en su propia superficie (coreai_dispatch_task / coreai_search_context,
contratos VECTORIZE_EVENT y RecallTextRequest extra=forbid).

Estos tests son el canario del mapeo: si el substrato cambia su
contrato (o la traducción se descamina), el fallo salta aquí en lugar de
en un chat de Telegram con el patrón esperando.
"""
import json
from unittest.mock import AsyncMock

import pytest

from src.bot.memory_tools import EDGE_TOOLS, MemoryTools

DISPATCH = {"task_id": "7f1b2c3d-0000-4000-8000-000000000001",
            "session_id": "sess-1", "status": "PENDING"}

def _memory_tools(client=None):
    client = client or AsyncMock()
    return MemoryTools(client, project="lifeos"), client

def _call(name, arguments) -> dict:
    return {
        "id": "call_1",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }

# --- superficie de borde ------------------------------------------------
def test_superficie_exacta_dos_tools():
    """La persona ve EXACTAMENTE memory_save y memory_recall: nada del
    catálogo del substrato (6 tools, admin de DLQ incluido) se filtra."""
    names = {t["function"]["name"] for t in EDGE_TOOLS}
    assert names == {"memory_save", "memory_recall"}

def test_schemas_declaran_argumento_y_closed_properties():
    for tool in EDGE_TOOLS:
        schema = tool["function"]["parameters"]
        assert schema["additionalProperties"] is False
        assert len(schema["required"]) == 1

# --- memory_save → coreai_dispatch_task --------------------------------

@pytest.mark.asyncio
async def test_save_traduce_a_dispatch_vectorize_event():
    mt, client = _memory_tools()
    client.call.return_value = json.dumps(DISPATCH)

    ok, text = await mt.execute(_call("memory_save", {"texto": "El jueves hay que llamar a Natalia"}), task="t1")

    assert ok is True
    assert DISPATCH["task_id"] in text
    client.call.assert_awaited_once_with(
        "coreai_dispatch_task",
        {"task_type": "vectorize_event",
         "task_payload": {"content": "El jueves hay que llamar a Natalia",
                          "project": "lifeos"}},
        "t1",
    )

@pytest.mark.asyncio
async def test_save_arg_extra_del_modelo_nunca_llega_al_substrato():
    """VECTORIZE_EVENT es extra=forbid: el modelo puede alucinar tantos
    argumentos como quiera — el payload al substrato sale SIEMPRE de dos
    claves. Esta es la guarda que acota el rango de error del LLM."""
    mt, client = _memory_tools()
    client.call.return_value = json.dumps(DISPATCH)

    ok, _ = await mt.execute(_call("memory_save", {"texto": "dato", "urgente": True}), task="t1")

    assert ok is True
    _name, args, _task = client.call.await_args.args
    assert set(args["task_payload"].keys()) == {"content", "project"}

@pytest.mark.asyncio
async def test_save_texto_vacio_no_abre_canal():
    mt, client = _memory_tools()
    ok, text = await mt.execute(_call("memory_save", {"texto": "   "}), task="t1")
    assert ok is False
    client.call.assert_not_awaited()

# --- memory_recall → coreai_search_context ------------------------------
def _hit(content="El jueves hay que llamar a Natalia", score=0.92):
    return {"point_id": "9c8b7a6d-0000-4000-8000-000000000002",
            "domain": "system", "score": score, "content": content,
            "session_id": None, "project": "lifeos"}

@pytest.mark.asyncio
async def test_recall_traduce_a_search_y_formatea_hits():
    mt, client = _memory_tools()
    client.call.return_value = json.dumps({"hits": [_hit()]})

    ok, text = await mt.execute(_call("memory_recall", {"consulta": "a quién tengo que llamar"}), task="t2")

    assert ok is True
    assert "llamar a Natalia" in text
    assert "0.92" in text
    client.call.assert_awaited_once_with(
        "coreai_search_context",
        {"query": "a quién tengo que llamar", "project": "lifeos", "top_k": 5},
        "t2",
    )

@pytest.mark.asyncio
async def test_recall_sin_hits_es_no_match_honesto_no_fallo():
    """Lista vacía = la memoria no miente con resultados flojos (umbral del
    substrato): ok=True y el modelo recibe la orden de no inventar."""
    mt, client = _memory_tools()
    client.call.return_value = json.dumps({"hits": []})

    ok, text = await mt.execute(_call("memory_recall", {"consulta": "x"}), task="t2")

    assert ok is True
    assert "Sin resultados" in text
    assert "NO inventes" in text

# --- fallos: NINGÚN path lanza, el loop es inmortal ---------------------

@pytest.mark.asyncio
async def test_fallo_de_substrato_se_devuelve_como_tool_error():
    from src.bot.mcp import SubstrateError
    client = AsyncMock()
    client.call.side_effect = SubstrateError("core-mcp caído")
    mt, _ = _memory_tools(client)

    ok, text = await mt.execute(_call("memory_save", {"texto": "dato"}), task="t3")

    assert ok is False
    assert "core-mcp caído" in text
    assert "reintentar" in text

@pytest.mark.asyncio
async def test_respuesta_de_dispatch_malformada_es_falso():
    client = AsyncMock()
    client.call.return_value = "esto no es JSON del substrato"
    mt, _ = _memory_tools(client)

    ok, text = await mt.execute(_call("memory_save", {"texto": "dato"}), task="t3")

    assert ok is False
    assert "forma inesperada" in text

@pytest.mark.asyncio
async def test_argumentos_json_invalidos_no_abre_canal():
    mt, client = _memory_tools()
    bad = {"id": "call_9", "type": "function",
           "function": {"name": "memory_save", "arguments": "{texto: roto"}}
    ok, text = await mt.execute(bad, task="t4")
    assert ok is False
    client.call.assert_not_awaited()

@pytest.mark.asyncio
async def test_tool_alucinada_fuera_de_superficie_se_rebota():
    mt, client = _memory_tools()
    ok, text = await mt.execute(_call("coreai_retry_failed_task", {"task_id": "x"}), task="t5")
    assert ok is False
    assert "desconocida" in text
    client.call.assert_not_awaited()
