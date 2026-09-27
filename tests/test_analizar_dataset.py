"""
Test básico para la herramienta analizar_dataset.
Verifica que la implementación funciona correctamente.
"""
import json
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.tools.dataset_analysis_tool import analizar_dataset, crear_dataset_analysis_tool


def test_analizar_dataset_valido():
    """Test de análisis de un dataset válido."""
    print("🧪 Test 1: Análisis de dataset válido (C018)")
    print("-" * 60)
    
    resultado = analizar_dataset("C018")
    datos = json.loads(resultado)
    
    # Verificaciones
    assert 'codigo' in datos, "Falta campo 'codigo'"
    assert datos['codigo'] == 'C018', f"Código incorrecto: {datos['codigo']}"
    
    assert 'titulo' in datos, "Falta campo 'titulo'"
    assert len(datos['titulo']) > 0, "Título vacío"
    
    assert 'columnas' in datos, "Falta campo 'columnas'"
    assert isinstance(datos['columnas'], list), "Columnas no es lista"
    assert len(datos['columnas']) > 0, "No hay columnas"
    
    assert 'filas' in datos, "Falta campo 'filas'"
    assert datos['filas'] > 0, "No hay filas"
    
    assert 'tipos_datos' in datos, "Falta campo 'tipos_datos'"
    assert len(datos['tipos_datos']) == len(datos['columnas']), "Mismatch en tipos de datos"
    
    assert 'muestra_datos' in datos, "Falta campo 'muestra_datos'"
    assert len(datos['muestra_datos']) <= 3, "Muestra excede 3 registros"
    
    assert 'columnas_numericas' in datos, "Falta campo 'columnas_numericas'"
    assert isinstance(datos['columnas_numericas'], list), "Columnas numéricas no es lista"
    
    assert 'metadata_adicional' in datos, "Falta campo 'metadata_adicional'"
    meta = datos['metadata_adicional']
    assert 'unidad' in meta, "Falta unidad en metadata"
    assert 'cobertura_temporal' in meta, "Falta cobertura temporal en metadata"
    
    print("✅ Todas las verificaciones pasaron")
    print(f"   • Código: {datos['codigo']}")
    print(f"   • Título: {datos['titulo']}")
    print(f"   • Filas: {datos['filas']:,}")
    print(f"   • Columnas: {len(datos['columnas'])}")
    print(f"   • Columnas numéricas: {len(datos['columnas_numericas'])}")
    print()
    return True


def test_analizar_dataset_invalido():
    """Test de análisis de un dataset inválido."""
    print("🧪 Test 2: Análisis de dataset inválido (XXXX)")
    print("-" * 60)
    
    resultado = analizar_dataset("XXXX_INVALIDO")
    datos = json.loads(resultado)
    
    # Verificaciones
    assert 'error' in datos, "Debería tener campo 'error'"
    assert datos['error'] == 'Dataset no encontrado', f"Error incorrecto: {datos['error']}"
    
    assert 'codigo_buscado' in datos, "Falta campo 'codigo_buscado'"
    assert datos['codigo_buscado'] == 'XXXX_INVALIDO', f"Código buscado incorrecto: {datos['codigo_buscado']}"
    
    assert 'mensaje' in datos, "Falta campo 'mensaje'"
    assert 'sugerencia' in datos, "Falta campo 'sugerencia'"
    
    print("✅ Manejo de errores funciona correctamente")
    print(f"   • Error: {datos['error']}")
    print(f"   • Mensaje: {datos['mensaje']}")
    print(f"   • Sugerencia: {datos['sugerencia']}")
    print()
    return True


def test_crear_function_tool():
    """Test de creación de FunctionTool."""
    print("🧪 Test 3: Creación de FunctionTool")
    print("-" * 60)
    
    tool = crear_dataset_analysis_tool()
    
    # Verificaciones
    assert tool is not None, "Tool es None"
    assert hasattr(tool, 'metadata'), "Tool no tiene metadata"
    assert tool.metadata.name == "analizar_dataset", f"Nombre incorrecto: {tool.metadata.name}"
    assert hasattr(tool.metadata, 'description'), "Tool no tiene descripción"
    assert len(tool.metadata.description) > 0, "Descripción vacía"
    
    print("✅ FunctionTool creada correctamente")
    print(f"   • Nombre: {tool.metadata.name}")
    print(f"   • Descripción: {tool.metadata.description[:100]}...")
    print()
    return True


def test_case_insensitive():
    """Test de que el código funciona con mayúsculas y minúsculas."""
    print("🧪 Test 4: Compatibilidad mayúsculas/minúsculas")
    print("-" * 60)
    
    # Probar con mayúsculas
    resultado_upper = analizar_dataset("C018")
    datos_upper = json.loads(resultado_upper)
    
    # Probar con minúsculas
    resultado_lower = analizar_dataset("c018")
    datos_lower = json.loads(resultado_lower)
    
    # Verificar que ambos retornan el mismo dataset
    assert datos_upper['codigo'] == datos_lower['codigo'], "Códigos no coinciden"
    assert datos_upper['titulo'] == datos_lower['titulo'], "Títulos no coinciden"
    assert datos_upper['filas'] == datos_lower['filas'], "Filas no coinciden"
    
    print("✅ Funciona correctamente con mayúsculas y minúsculas")
    print(f"   • 'C018' → {datos_upper['codigo']}")
    print(f"   • 'c018' → {datos_lower['codigo']}")
    print()
    return True


def main():
    """Ejecutar todos los tests."""
    print("\n" + "="*60)
    print("🚀 TESTS: Herramienta analizar_dataset")
    print("="*60 + "\n")
    
    tests = [
        test_analizar_dataset_valido,
        test_analizar_dataset_invalido,
        test_crear_function_tool,
        test_case_insensitive
    ]
    
    resultados = []
    
    for test in tests:
        try:
            resultado = test()
            resultados.append((test.__name__, resultado, None))
        except Exception as e:
            print(f"❌ Error en {test.__name__}: {e}\n")
            resultados.append((test.__name__, False, str(e)))
    
    # Resumen
    print("="*60)
    print("📊 RESUMEN DE TESTS")
    print("="*60)
    
    exitosos = sum(1 for _, resultado, _ in resultados if resultado)
    total = len(resultados)
    
    for nombre, resultado, error in resultados:
        status = "✅ PASS" if resultado else "❌ FAIL"
        print(f"{status} - {nombre}")
        if error:
            print(f"      Error: {error}")
    
    print()
    print(f"Total: {exitosos}/{total} tests exitosos")
    
    if exitosos == total:
        print("\n🎉 Todos los tests pasaron correctamente!")
        return 0
    else:
        print(f"\n⚠️  {total - exitosos} test(s) fallaron")
        return 1


if __name__ == "__main__":
    exit(main())
