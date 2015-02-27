
def group_0_adder_edgeattrn12n135():
    rediskeylist = ['edgeattr:n1@n1', 'edgeattr:n1@n2', 'edgeattr:n1@n3', 'edgeattr:n1@n5', 'edgeattr:n2@n1', 'edgeattr:n2@n2', 'edgeattr:n2@n3', 'edgeattr:n2@n5']
    valstring = {"outport": None, "inport": None}
    return (rediskeylist, valstring)

def group_1_update_category(rediskey, jsonobj):
    e = jsonobj
    assert(e is not None)
    def test_del_category():
        if e['category'] == "A": 
            return True 
        else: 
            return False
    if test_del_category():
        del e['category']
    return (rediskey, jsonobj)

def group_1_update__id(rediskey, jsonobj):
    e = jsonobj
    assert(e is not None)
    tmp = e['_id']
    
    if any(c.isalpha() for c in tmp): 
        e['_id']=int(tmp, 16)
    return (rediskey, jsonobj)

def group_1_update_order(rediskey, jsonobj):
    e = jsonobj.get('order').get('orderItems')
    assert(e is not None)
    for f in e:
        assert(f is not None)
        f['discountedPrice'] = round(f['price']*.7,2)
        f['fullprice'] = f.pop('price')
    return (rediskey, jsonobj)

def group_2_update_outport(rediskey, jsonobj):
    e = jsonobj
    assert(e is not None)
    tmp = e['outport']
    e['outport'] = 777
    return (rediskey, jsonobj)

def get_update_tuples():
    return [('key:*', ['group_1_update_category', 'group_1_update__id', 'group_1_update_order'], 'key', 'ver0', 'ver1'), ('edgeattr:n*@n5', ['group_2_update_outport'], 'edgeattr', 'v0', 'v1')]
def get_newkey_tuples():
    return [('edgeattr:n[1-2]@n[1-3,5]', ['group_0_adder_edgeattrn12n135'], 'edgeattr', 'v1')]