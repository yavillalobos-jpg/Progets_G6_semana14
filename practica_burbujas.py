import time
import random

def generar_intervalos(cantidad):
    elementos = [
        max(1, cantidad // 4),
        max(1, cantidad // 2),
        cantidad
    ]
    return sorted(set(elementos))

def generar_numeros(cantidad):
    inicio = time.perf_counter()
    datos = [random.randint(0, 1_000_000_000) for _ in range(cantidad)]
    fin = time.perf_counter()
    tiempo = fin - inicio
    return datos, tiempo

def sort(lista):
    n = len(lista)
    for i in range(n):
        for j in range(0, n - i - 1):
            if lista[j] > lista[j + 1]:
                lista[j], lista[j + 1] = lista[j + 1], lista[j]
    return lista


cantidad = int(input("Cantidad de elementos: "))
print("Iniciar generación...")
datos, tiempo_gen = generar_numeros(cantidad)
print(f"Tiempo de generación: {tiempo_gen:.4f} segundos")
print("Fin de generación")
print("\nLista original (primeros 20 elementos):")
print(datos[:20])
print("\nOrdenando...")
ini = time.perf_counter()
datos_ordenados = sort(datos.copy())
fin = time.perf_counter()
print(f"Tiempo de ordenamiento (burbuja): {fin - ini:.4f} segundos")
print("\nLista ordenada (primeros 20 elementos):")
print(datos_ordenados[:20])
input("Presione cualquier tecla para continuar...")