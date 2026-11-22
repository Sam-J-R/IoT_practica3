"""Tabla tendedero_vinculaciones en memoria (clave userId + thingName).

Imita solo las llamadas que hace la Lambda de Alexa: query por userId,
put_item, update_item con ConditionExpression y delete_item.
"""


class CondicionFallida(Exception):
    def __init__(self):
        super().__init__("ConditionalCheckFailedException")
        self.response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class TablaVinculaciones:
    def __init__(self):
        self.items = {}  # (userId, thingName) -> item
        self.llamadas = []

    def de(self, user_id):
        """Items del usuario, como diccionario thingName -> item."""
        return {t: i for (u, t), i in self.items.items() if u == user_id}

    def query(self, KeyConditionExpression, ExpressionAttributeValues, ConsistentRead=False):
        assert KeyConditionExpression == "userId = :u", KeyConditionExpression
        assert ConsistentRead, "la Lambda debe leer con consistencia fuerte"
        self.llamadas.append("query")
        usuario = ExpressionAttributeValues[":u"]
        return {"Items": [dict(i) for (u, _), i in sorted(self.items.items()) if u == usuario]}

    def put_item(self, Item):
        self.llamadas.append("put_item")
        self.items[(Item["userId"], Item["thingName"])] = dict(Item)

    def update_item(self, Key, UpdateExpression, ConditionExpression, ExpressionAttributeValues):
        assert UpdateExpression == "SET fechaSeleccion = :f", UpdateExpression
        self.llamadas.append("update_item")
        clave = (Key["userId"], Key["thingName"])
        if clave not in self.items:
            raise CondicionFallida()
        self.items[clave]["fechaSeleccion"] = ExpressionAttributeValues[":f"]

    def delete_item(self, Key):
        self.llamadas.append("delete_item")
        self.items.pop((Key["userId"], Key["thingName"]), None)
