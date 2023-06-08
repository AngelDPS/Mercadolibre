def obtener_codigo(evento):
    match evento[0]["dynamodb"]["NewImage"]["entity"]["S"]:
        case "articulos":
            return evento[0]["dynamodb"]["NewImage"]["co_art"]["S"]
        case _:
            return None
