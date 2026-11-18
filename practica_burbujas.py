from hub import port, motion_sensor, light_matrix
import runloop
import motor
import motor_pair
import color_sensor
import color
import distance_sensor

# ==========================================
# CONFIGURACIÓN Y CALIBRACIÓN (EN CM)
# ==========================================
CIRCUNFERENCIA_LLANTA_CM = 17.6

GRADOS_GARRA = 160
VELOCIDAD_GARRA = 350
VELOCIDAD_BASE = 420
KP = 3                  # qué tan fuerte corrige para ir derecho
MARGEN_GIRO = 1         # grados antes del objetivo en que se frena

# Ultrasónico: se detiene cuando ve el bloque a esta distancia o menos (mm).
# Miren en la consola los valores "dist" para elegir el número correcto.
DIST_PARAR_MM = 60
USAR_COLOR_PARA_PARAR = False   # el sensor mira al piso: ve las rayas rojas y el cuadro amarillo

# Signo del giroscopio al girar a la derecha. Se mide UNA sola vez en el primer giro de 90°.
SIGNO_DERECHA = -1
signo_medido = False

# Cuánto avanzaba el robot hacia cada bloque cuando ustedes calibraron 42 y 36
# (antes el ultrasónico casi nunca veía el bloque, así que llegaba al máximo).
# Si el robot ahora se detiene antes, se compensa solo: avanza (r - R_REF) menos al cuadro.
R_REF_ROJO = 22
R_REF_AMARILLO = 32
R_REF_AZUL = 32
R_REF_VERDE = 32

motor_pair.pair(motor_pair.PAIR_1, port.C, port.D)

# ==========================================
# FUNCIONES DE MOVIMIENTO Y GARRA
# ==========================================
def cm_a_grados(cm):
    return int((cm / CIRCUNFERENCIA_LLANTA_CM) * 360)

def grados_a_cm(grados):
    return grados * CIRCUNFERENCIA_LLANTA_CM / 360

def recorrido_grados():
    return (abs(motor.relative_position(port.C)) + abs(motor.relative_position(port.D))) / 2

def yaw():
    return motion_sensor.tilt_angles()[0] / 10

def desvio():
    # + = el robot se fue hacia la derecha
    return SIGNO_DERECHA * yaw()

async def mover_cm(cm, velocidad=VELOCIDAD_BASE):
    """Va recto con giroscopio, arranca y frena suave."""
    if abs(cm) < 0.5:
        return
    motion_sensor.reset_yaw(0)
    motor.reset_relative_position(port.C, 0)
    motor.reset_relative_position(port.D, 0)
    await runloop.sleep_ms(50)
    signo = 1 if cm > 0 else -1
    objetivo = abs(cm_a_grados(cm))
    while True:
        hecho = recorrido_grados()
        falta = objetivo - hecho
        if falta <= 0:
            break
        v = min(velocidad, 150 + hecho * 2, 100 + falta * 2)
        corr = 0
        if signo_medido:            # solo corrige cuando ya sabe el signo del giroscopio
            corr = max(-30, min(30, int(-desvio() * KP))) * signo
        motor_pair.move(motor_pair.PAIR_1, corr, velocity=int(v * signo))
        await runloop.sleep_ms(10)
    motor_pair.stop(motor_pair.PAIR_1, stop=motor.HOLD)
    await runloop.sleep_ms(100)

async def girar(grados, lado):
    """lado = 1 derecha, -1 izquierda.
    Suma el ángulo poco a poco, así funciona igual en 90° que en 180°
    (el giroscopio salta de +180 a -180 y antes eso lo volvía loco)."""
    global SIGNO_DERECHA, signo_medido
    motion_sensor.reset_yaw(0)
    await runloop.sleep_ms(60)
    girado = 0
    anterior = yaw()
    tiempo = 0
    while tiempo < 5000:
        actual = yaw()
        d = actual - anterior
        if d > 180:
            d -= 360
        if d < -180:
            d += 360
        girado += d
        anterior = actual
        falta = grados - abs(girado)
        if falta <= MARGEN_GIRO:
            break
        v = 220 if falta > 30 else 80
        motor_pair.move_tank(motor_pair.PAIR_1, v * lado, -v * lado)
        await runloop.sleep_ms(5)
        tiempo += 5
    motor_pair.stop(motor_pair.PAIR_1, stop=motor.HOLD)
    await runloop.sleep_ms(150)
    if not signo_medido and grados <= 120 and abs(girado) > 45:
        SIGNO_DERECHA = (1 if girado > 0 else -1) * lado
        signo_medido = True

async def girar_derecha(grados=90):
    await girar(grados, 1)

async def girar_izquierda(grados=90):
    await girar(grados, -1)

async def subir_garra():
    await motor.run_for_degrees(port.E, GRADOS_GARRA, VELOCIDAD_GARRA)
    await runloop.sleep_ms(100)

async def bajar_garra():
    await motor.run_for_degrees(port.E, -GRADOS_GARRA, VELOCIDAD_GARRA)
    await runloop.sleep_ms(100)

async def avanzar_hasta_bloque(color_objetivo, distancia_max_cm=30):
    """Avanza recto hasta el bloque y DEVUELVE cuántos cm avanzó."""
    motion_sensor.reset_yaw(0)
    motor.reset_relative_position(port.C, 0)
    motor.reset_relative_position(port.D, 0)
    await runloop.sleep_ms(50)
    grados_max = abs(cm_a_grados(distancia_max_cm))
    vio = "max"
    while True:
        dist_mm = distance_sensor.distance(port.F)      # -1 = no ve nada
        if 0 < dist_mm <= DIST_PARAR_MM:
            vio = "ultra"
            break
        if USAR_COLOR_PARA_PARAR and color_sensor.color(port.A) == color_objetivo:
            vio = "color"
            break
        if recorrido_grados() >= grados_max:
            break
        corr = max(-30, min(30, int(-desvio() * KP)))
        motor_pair.move(motor_pair.PAIR_1, corr, velocity=200)
        await runloop.sleep_ms(10)
    motor_pair.stop(motor_pair.PAIR_1, stop=motor.HOLD)
    await runloop.sleep_ms(100)
    avance = grados_a_cm(recorrido_grados())
    print("bloque", color_objetivo, "avanzo", round(avance, 1), "cm, paro por", vio,
          "dist", distance_sensor.distance(port.F))
    light_matrix.write(str(int(avance)))
    return avance

# ==========================================
# RECORRIDO COMPLETO DEL MAPA (los números de ustedes)
# ==========================================
async def main():
    # ---------------- 1. RUTA ROJA ----------------
    await mover_cm(52)
    await girar_izquierda(90)
    await mover_cm(52)

    r = await avanzar_hasta_bloque(color.RED, distancia_max_cm=22)
    await bajar_garra()

    await mover_cm(-6)
    await girar_derecha(90)
    await mover_cm(18)
    await girar_derecha(90)
    await mover_cm(42 + (r - R_REF_ROJO))
    await subir_garra()

    # ---------------- 2. RUTA AMARILLA ----------------
    await mover_cm(-18)
    await girar_derecha(90)
    await mover_cm(24)
    await girar_derecha(90)

    r = await avanzar_hasta_bloque(color.YELLOW, distancia_max_cm=32)
    await bajar_garra()

    await girar_derecha(180)
    await mover_cm(36 + (r - R_REF_AMARILLO))
    await subir_garra()

    # ---------------- 3. RUTA AZUL ----------------
    await mover_cm(-12)
    await girar_derecha(90)
    await mover_cm(22)
    await girar_derecha(90)

    r = await avanzar_hasta_bloque(color.BLUE, distancia_max_cm=32)
    await bajar_garra()

    await girar_derecha(180)
    await mover_cm(36 + (r - R_REF_AZUL))
    await subir_garra()

    # ---------------- 4. RUTA VERDE ----------------
    await mover_cm(-12)
    await girar_derecha(90)
    await mover_cm(22)
    await girar_derecha(90)

    r = await avanzar_hasta_bloque(color.GREEN, distancia_max_cm=32)
    await bajar_garra()

    await girar_derecha(180)
    await mover_cm(36 + (r - R_REF_VERDE))
    await subir_garra()
    await mover_cm(-10)

runloop.run(main())