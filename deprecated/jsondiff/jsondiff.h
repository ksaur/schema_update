#ifndef JSONDIFF_H
#define JSONDIFF_H

typedef enum {SET_CMD, DEL_CMD} command;
#define SET_CMD_STR "  json_object_set(obj, "
#define DEL_CMD_STR "  json_object_del(obj, "


#define DEFINE_KEY "setofdefines"
#define TOP_DECLS_KEY "setoftopdecls"

void diff_objects(json_t * old, json_t * new, const char *root);

#endif
