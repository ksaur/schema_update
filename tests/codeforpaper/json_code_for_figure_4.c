#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>     /* assert */
#include <hiredis/hiredis.h>
#include <jansson.h>

char * k = "mykey:1";
char * v = "{ \"_id\": \"4bd8ae97c47016442af4a580\", \"customerid\": 99999, \"name\": \"Foo Sushi Inc\", \"since\": \"12/12/2001\", \"category\": \"A\", \"order\": { \"orderid\": \"UXWE-122012\", \"orderdate\": \"12/12/2001\", \"orderItems\": [ { \"product\": \"Fortune Cookies\", \"price\": 19.99 } ] } }";

void test_fun_updval(char ** key, void ** value, 
                                size_t * val_len){
  json_t *root, *arr, *ele, *price;
  int i;
  double pval;
  json_error_t error;
  char * jstr = (char*)*value;
  root = json_loads(jstr, 0, &error);
  arr = json_object_get(json_object_get(root, "order"), "orderItems");
  for(i = 0; i < json_array_size(arr); i++){
     ele = json_array_get(arr, i);
     price = json_object_get(ele, "price");
     json_object_set(ele, "discountedPrice", json_real(json_real_value(price)-3.0));
     json_object_set(ele, "fullPrice", price);
     json_object_del(ele, "price");
  }
  *value = json_dumps(root,0);
  *val_len = strlen(*value); 
} 


int main(void){

  size_t s = strlen(v);
  printf("%d\n", (int)s);
  test_fun_updval(&k, (void**)&v, &s); 
  printf("%s\n", v);
  printf("%d\n", (int)s);
  return 0;
}
