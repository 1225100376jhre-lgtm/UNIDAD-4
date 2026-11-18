
# U4ACT03 - DevOps con Python
# Autor: JAIRO ROSAS ENRIQUEZ

def es_correo_valido(correo):
    """Devuelve True si el correo tiene @ y un punto despues del @."""

    if "@" not in correo:
        return False

    usuario, dominio = correo.split("@", 1)

    if usuario == "" or "." not in dominio:
        return False

    return True
