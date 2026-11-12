
# U4ACT02 - RESTCONF with Python y Tkinter
# Autor: JAIRO ROSAS ENRIQUEZ
# Desafios 1, 2, 3 y 4

import json
import requests
import tkinter as tk
from tkinter import messagebox
from getpass import getpass
from ipaddress import IPv4Address, IPv4Network
from urllib.parse import quote
from threading import Thread
from queue import Queue, Empty

# Desactivar advertencias SSL (solo laboratorio)
requests.packages.urllib3.disable_warnings()

# Datos del Cisco Catalyst 8000V
router_ip = "10.10.20.48"
usuario = "developer"
contrasena = getpass("Contrasena del router: ")
basicauth = (usuario, contrasena)

headers = {
    "Accept": "application/yang-data+json",
    "Content-type": "application/yang-data+json"
}

base_url = (
    f"https://{router_ip}/restconf/data/"
    "ietf-interfaces:interfaces/interface="
)

cola_respuestas = Queue()
ocupado = False


# DESAFIO 4: BARRA DE ESTADO
def actualizar_estado(mensaje, correcto=False):
    color = "#198754" if correcto else "#dc3545"
    barra_estado.config(
        text=mensaje,
        bg=color,
        fg="white"
    )


def cambiar_botones(habilitados):
    estado = tk.NORMAL if habilitados else tk.DISABLED

    boton_get.config(state=estado)
    boton_put.config(state=estado)
    boton_delete.config(state=estado)


def mensaje_error(codigo):
    errores = {
        400: "400 - Solicitud incorrecta",
        401: "401 - Error de autenticacion",
        403: "403 - Acceso denegado",
        404: "404 - Interfaz no encontrada",
        500: "500 - Error interno del servidor"
    }

    return errores.get(
        codigo,
        f"Error HTTP {codigo}"
    )


# EJECUTAR SOLICITUD SIN CONGELAR TKINTER
def ejecutar_solicitud(metodo, nombre, datos=None):
    global ocupado

    if ocupado:
        return

    ocupado = True
    cambiar_botones(False)

    barra_estado.config(
        text="Procesando solicitud RESTCONF...",
        bg="#d9a227",
        fg="black"
    )

    url = base_url + quote(nombre, safe="")

    hilo = Thread(
        target=trabajador_restconf,
        args=(metodo, url, datos, nombre),
        daemon=True
    )
    hilo.start()


def trabajador_restconf(metodo, url, datos, nombre):
    try:
        opciones = {
            "auth": basicauth,
            "headers": headers,
            "verify": False,
            "timeout": 10
        }

        if metodo == "GET":
            resp = requests.get(url, **opciones)

        elif metodo == "PUT":
            resp = requests.put(
                url,
                data=json.dumps(datos),
                **opciones
            )

        elif metodo == "DELETE":
            resp = requests.delete(url, **opciones)

        else:
            return

        contenido = None

        if metodo == "GET" and resp.status_code == 200:
            contenido = resp.json()

        cola_respuestas.put({
            "metodo": metodo,
            "nombre": nombre,
            "codigo": resp.status_code,
            "datos": contenido,
            "error": None
        })

    except (requests.exceptions.RequestException,
            ValueError, TypeError) as error:

        cola_respuestas.put({
            "metodo": metodo,
            "nombre": nombre,
            "codigo": None,
            "datos": None,
            "error": str(error)
        })


# PROCESAR RESPUESTA EN LA VENTANA
def procesar_respuestas():
    global ocupado

    try:
        while True:
            respuesta = cola_respuestas.get_nowait()

            ocupado = False
            cambiar_botones(True)

            metodo = respuesta["metodo"]
            nombre = respuesta["nombre"]
            codigo = respuesta["codigo"]
            error = respuesta["error"]

            if error:
                actualizar_estado(
                    "Error de conexion o respuesta: " + error
                )
                messagebox.showerror(
                    "Error RESTCONF",
                    error
                )
                continue

            if metodo == "GET" and codigo == 200:
                try:
                    datos = respuesta["datos"]
                    interfaz = datos["ietf-interfaces:interface"]

                    if isinstance(interfaz, list):
                        interfaz = interfaz[0]

                    ipv4 = interfaz.get("ietf-ip:ipv4", {})
                    direcciones = ipv4.get("address", [])

                    if direcciones:
                        ip = direcciones[0].get(
                            "ip", "Sin IP"
                        )
                        mascara = direcciones[0].get(
                            "netmask", "No disponible"
                        )
                    else:
                        ip = "Sin IP"
                        mascara = "No disponible"

                    estado = (
                        "Habilitada"
                        if interfaz.get("enabled", False)
                        else "Deshabilitada"
                    )

                    resultados.delete("1.0", tk.END)
                    resultados.insert(
                        tk.END,
                        f"INTERFAZ: {nombre}\n"
                        f"DIRECCION IP: {ip}\n"
                        f"MASCARA: {mascara}\n"
                        f"ESTADO ADMINISTRATIVO: {estado}\n"
                        f"HTTP STATUS: {codigo}\n"
                    )

                    actualizar_estado(
                        "Operacion exitosa - HTTP 200",
                        True
                    )

                except (KeyError, IndexError,
                        TypeError, AttributeError) as error:
                    actualizar_estado(
                        "Error al interpretar la respuesta"
                    )
                    messagebox.showerror(
                        "Error de datos",
                        str(error)
                    )

            elif metodo == "PUT" and codigo in (200, 201):
                resultados.delete("1.0", tk.END)
                resultados.insert(
                    tk.END,
                    f"INTERFAZ: {nombre}\n"
                    f"CREADA / ACTUALIZADA\n"
                    f"HTTP STATUS: {codigo}\n"
                )

                actualizar_estado(
                    f"Operacion exitosa - HTTP {codigo}",
                    True
                )

                messagebox.showinfo(
                    "Operacion exitosa",
                    f"Interfaz {nombre} creada/actualizada.\n"
                    f"HTTP STATUS: {codigo}"
                )

            elif metodo == "DELETE" and codigo in (200, 202, 204):
                resultados.delete("1.0", tk.END)
                resultados.insert(
                    tk.END,
                    f"INTERFAZ ELIMINADA: {nombre}\n"
                    f"HTTP STATUS: {codigo}\n"
                )

                actualizar_estado(
                    f"Operacion exitosa - HTTP {codigo}",
                    True
                )

                messagebox.showinfo(
                    "Eliminacion exitosa",
                    f"Interfaz {nombre} eliminada.\n"
                    f"HTTP STATUS: {codigo}"
                )

            else:
                error_http = mensaje_error(codigo)

                actualizar_estado(error_http)

                messagebox.showerror(
                    "Error RESTCONF",
                    error_http
                )

    except Empty:
        pass

    ventana.after(100, procesar_respuestas)


# DESAFIO 1: CONSULTA GET
def consultar_interfaz():
    nombre = entrada_nombre.get().strip()

    if not nombre:
        messagebox.showwarning(
            "Advertencia",
            "Escribe el nombre de una interfaz."
        )
        return

    ejecutar_solicitud("GET", nombre)


# VALIDAR NOMBRE DE LOOPBACK
def loopback_valida(nombre):
    return (
        nombre.startswith("Loopback")
        and nombre[8:].isdigit()
    )


# DESAFIO 2: CREACION PUT
def crear_interfaz():
    nombre = entrada_nombre.get().strip()
    ip = entrada_ip.get().strip()
    mascara = entrada_mascara.get().strip()
    descripcion = entrada_descripcion.get().strip()

    if not all((nombre, ip, mascara, descripcion)):
        messagebox.showwarning(
            "Campos incompletos",
            "Completa todos los campos."
        )
        return

    if not loopback_valida(nombre):
        messagebox.showwarning(
            "Interfaz no permitida",
            "Esta practica solo configura Loopback."
        )
        return

    try:
        IPv4Address(ip)
        IPv4Network(f"0.0.0.0/{mascara}")
    except ValueError:
        messagebox.showerror(
            "Datos incorrectos",
            "Revisa la IP y la mascara."
        )
        return

    # Construccion dinamica de yangConfig
    yangConfig = {
        "ietf-interfaces:interface": {
            "name": nombre,
            "description": descripcion,
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {
                        "ip": ip,
                        "netmask": mascara
                    }
                ]
            },
            "ietf-ip:ipv6": {}
        }
    }

    ejecutar_solicitud("PUT", nombre, yangConfig)


# DESAFIO 3: ELIMINACION DELETE
def eliminar_interfaz():
    nombre = entrada_nombre.get().strip()

    if not loopback_valida(nombre):
        messagebox.showwarning(
            "Interfaz no permitida",
            "Escribe una interfaz Loopback valida."
        )
        return

    confirmar = messagebox.askyesno(
        "Confirmar eliminacion",
        f"¿Deseas eliminar la interfaz {nombre}?"
    )

    if not confirmar:
        return

    ejecutar_solicitud("DELETE", nombre)


# VENTANA PRINCIPAL
ventana = tk.Tk()
ventana.title("U4ACT02 - RESTCONF with Python")
ventana.geometry("720x710")

tk.Label(
    ventana,
    text="CLIENTE RESTCONF CON TKINTER",
    font=("Arial", 17, "bold")
).pack(pady=12)

tk.Label(
    ventana,
    text="ALUMNO: JAIRO ROSAS ENRIQUEZ",
    font=("Arial", 11, "bold")
).pack(pady=5)

tk.Label(
    ventana,
    text="Cisco Catalyst 8000V - 10.10.20.48"
).pack(pady=5)

# FORMULARIO
formulario = tk.Frame(ventana)
formulario.pack(pady=10)

campos = [
    ("Nombre de Interfaz:", "Loopback99"),
    ("Direccion IP:", "99.99.99.99"),
    ("Mascara:", "255.255.255.0"),
    ("Descripcion:", "U4ACT02 RESTCONF TKINTER")
]

entradas = []

for fila, (texto, valor) in enumerate(campos):
    tk.Label(
        formulario,
        text=texto
    ).grid(row=fila, column=0, padx=8, pady=6, sticky="e")

    entrada = tk.Entry(formulario, width=35)
    entrada.grid(row=fila, column=1, pady=6)
    entrada.insert(0, valor)
    entradas.append(entrada)

entrada_nombre = entradas[0]
entrada_ip = entradas[1]
entrada_mascara = entradas[2]
entrada_descripcion = entradas[3]

# BOTONES
boton_get = tk.Button(
    ventana,
    text="Consultar Interfaz (GET)",
    width=32,
    command=consultar_interfaz
)
boton_get.pack(pady=5)

boton_put = tk.Button(
    ventana,
    text="Crear/Actualizar Interfaz (PUT)",
    width=32,
    command=crear_interfaz
)
boton_put.pack(pady=5)

boton_delete = tk.Button(
    ventana,
    text="Eliminar Interfaz (DELETE)",
    width=32,
    command=eliminar_interfaz
)
boton_delete.pack(pady=5)

tk.Label(
    ventana,
    text="RESULTADOS RESTCONF",
    font=("Arial", 11, "bold")
).pack(pady=8)

resultados = tk.Text(
    ventana,
    width=72,
    height=9
)
resultados.pack(pady=5)

# DESAFIO 4: BARRA DE ESTADO INFERIOR
barra_estado = tk.Label(
    ventana,
    text="Esperando operacion RESTCONF...",
    bg="#6c757d",
    fg="white",
    font=("Arial", 10, "bold"),
    pady=10
)
barra_estado.pack(side=tk.BOTTOM, fill=tk.X)

# Comprobar respuestas sin bloquear la ventana
ventana.after(100, procesar_respuestas)

ventana.mainloop()
