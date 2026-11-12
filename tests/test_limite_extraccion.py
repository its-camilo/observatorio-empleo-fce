from observatorio.db.modelos import Ejecucion
from observatorio.orquestador import limite_extraccion_corrida


def test_limite_desde_ejecucion_congelado():
    ejec = Ejecucion(id_ejecucion="x", semestre="2026-II", corte="Inicio", parametros={"limite_extraccion_corrida": 100})
    assert limite_extraccion_corrida({"limite_extraccion_corrida": 0}, ejec) == 100


def test_limite_desde_config_si_ejecucion_sin_parametro():
    ejec = Ejecucion(id_ejecucion="x", semestre="2026-II", corte="Inicio")
    assert limite_extraccion_corrida({"limite_extraccion_corrida": 50}, ejec) == 50
    assert limite_extraccion_corrida({"limite_extraccion_corrida": 0}, ejec) == 0
