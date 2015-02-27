Original Schema:   [("key", "ver0"), ("edgeattr", "v0")]


Key Schema:  "key:X"  (for some 'X')
Value JSON Schema:
{
    "_id": "4bd8ae97c47016442af4a580",
    "customerid": 99999,
    "name": "Foo Sushi Inc",
    "since": "12/12/2001",
    "category": "A",
    "order": {
        "orderid": "UXWE-122012",
        "orderdate": "12/12/2001",
        "orderItems": [
            {
                "product": "Fortune Cookies",
                "price": 19.99
            }
        ]
    }
}


Key Schema: "edgeattr:nX@nX" (for some 'X')
Value JSON Schema:
{"outport": None, "inport": None}

==================================================

New Schema:   [("key", "ver1"), ("edgeattr", "v1")]


Key Schema:  "key:X"  (for some 'X')
Value JSON Schema:
{
    "_id": "23473328205018852615364322688",  // updated to be decimal only
    "customerid": 99999,
    "name": "India House",
    "since": "12/12/2012",
    //"category" is deleted, depending on the value of category (if it is "A")
    "order": {
        "orderid": "4821-UXWE-222012",
        "orderdate": "12/12/2001",
        "orderItems": [
            {
                "product": "Fortune Cookies",
                "fullprice": 19.99, // renamed from "price"
                "discountedPrice": 13.99 // added as a percetage of fullprice
            }
        ]
    }
}


Key Schema: "edgeattr:nX@nX" (for some 'X')
Value JSON Schema:
{"outport": (integer that is not None), "inport": (integer that is not None)}

