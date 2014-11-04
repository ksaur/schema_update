/*
 * ksaur: Diff two JSON files, output C code to run the diff using Jansson.
 *
 * This uses the Jansson library: (https://github.com/akheron/jansson)
 *
 * Jansson is free software; you can redistribute it and/or modify
 * it under the terms of the MIT license. See LICENSE for details.
 */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include <jansson.h>


/* Diff two JSON objects */
void diff_objects(json_t * old, json_t * new, const char *root){

	const char *key;
	json_t *value;
	char buffer[2000]; //TODO make robust
	int j = 0; //buffer ptr

	if(root == NULL && (!json_is_object(new) || !json_is_object(old))){
		printf("ERROR  Old and New should both be roots....\n");
		return;
	}

	/* TODO, do we want to store these in a huge hashtable? And then check for
	 * dupes? We don't want the structure to print multiple times...*/

	/* Print the header */
	if(root !=NULL)
		j += sprintf(buffer+j, "struct upd_%s{\n", root);
	
	/* Iterate over every key-value pair of object 
	 *  This loop checks for objects in the NEW that are not present 
	 *  in the OLD */
	json_object_foreach(new, key, value){
		json_t * oldvalue = json_object_get(old, key);
		if(json_is_object(value)){
			if(oldvalue == NULL)
				j += sprintf(buffer+j, "\tjson_object_set(out, "
					"\"%s\", DEFAULT_%s);\n", key, key);
			else  // oldvalue is not NULL
				diff_objects(oldvalue, value, key);
		}
        else if(json_is_string(value) || json_is_number(value) || 
				json_is_boolean(value) || json_is_null(value)){
			//printf("Found string = %s\n", key);
			if(oldvalue == NULL)
				j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
		}
        else if(json_is_array(value)){
			//printf("Found array = %s\n", key);
			if(oldvalue == NULL)
				printf("OMG TOODO (%s)\n", key);
			/* TODO: for now, just going to process the FIRST element of the
			   array.  I'm not sure yet what our stated assumptions will be.
			   Currently I'm assuming that all array elements are identical,
			   and that the number of array elements does not matter. */

			/* get and process the head array element */
			// TODO TESTING
			else  // oldvalue is not NULL
				diff_objects(json_array_get(oldvalue,  0), json_array_get(value,  0), NULL);
		}
	}
	/* Iterate over every key-value pair of object 
	 *  This loop checks for objects in the OLD that are not present 
	 *  in the NEW */
	//TODO fixup
	//json_object_foreach(old, key, value){
	//	json_t * newvalue = json_object_get(new, key);
	//	if(json_is_object(value)){
	//		if(newvalue == NULL)
	//			j += sprintf(buffer+j, "\tjson_object_set(out, "
	//				"\"%s\", DEFAULT_%s);\n", key, key);
	//		else  // oldvalue is not NULL
	//			diff_objects(newvalue, value, key);
	//	}
    //    else if(json_is_string(value) || json_is_number(value) || 
	//			json_is_boolean(value) || json_is_null(value)){
	//		//printf("Found string = %s\n", key);
	//		if(newvalue == NULL)
	//			j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
	//	}
    //    else if(json_is_array(value)){
	//		//printf("Found array = %s\n", key);
	//		if(newvalue == NULL)
	//			printf("OMG TOODO (%s)\n", key);
	//		/* TODO: for now, just going to process the FIRST element of the
	//		   array.  I'm not sure yet what our stated assumptions will be.
	//		   Currently I'm assuming that all array elements are identical,
	//		   and that the number of array elements does not matter. */

	//		/* get and process the head array element */
	//		// TODO TESTING
	//		else  // oldvalue is not NULL
	//			diff_objects(json_array_get(value,  0), json_array_get(newvalue,  0), NULL);
	//	}
	//}
	/* Print the trailer*/
	if(root !=NULL)
	  j += sprintf(buffer+j, "};\n");
    if(j>0)
	  printf("%s\n", buffer);
}


// TODO....do we need to do something special for each type? This version spells them all out.
//        else if(json_is_string(value)){
//			//printf("Found string = %s\n", key);
//			if(oldvalue == NULL)
//				j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//		}
//        else if(json_is_number(value)){
//			//printf("Found number = %s\n", key);
//			if(oldvalue == NULL)
//				j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//		}
//        else if(json_is_boolean(value)){
//			//printf("Found boolean = %s\n", key);
//			if(oldvalue == NULL)
//				j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//		}
//        else if(json_is_null(value)){
//			//printf("Found null = %s\n", key);
//			if(oldvalue == NULL)
//				j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//		}

/* Print JSON keys to string (ignore values, not necessary. */
void print_object(json_t * data){
	const char *key;
	json_t *value;

	// TODO Assertions that this is an object (not sure about that assumption)
	// ...need more test data.

	/* Iterate over every key-value pair of object */
	json_object_foreach(data, key, value){
		if(json_is_object(value)){
			printf("Found object = %s\n", key);
			print_object(value);
		}
        else if(json_is_string(value))
			printf("Found string = %s\n", key);
        else if(json_is_number(value))
			printf("Found number = %s\n", key);
        else if(json_is_boolean(value))
			printf("Found boolean = %s\n", key);
        else if(json_is_null(value))
			printf("Found null = %s\n", key);
        else if(json_is_array(value)){
			printf("Found array = %s\n", key);
			/* TODO: for now, just going to process the FIRST element of the
			   array.  I'm not sure yet what our stated assumptions will be.
			   Currently I'm assuming that all array elements are identical,
			   and that the number of array elements does not matter. */

			/* get and process the head array element */
			print_object(json_array_get(value, 0));
		}
	}
}


char * request(char * filename){

	/*http://stackoverflow.com/questions/2029103/
		correct-way-to-read-a-text-file-into-a-buffer-in-c*/
	char * buf = NULL;
	FILE *fp = fopen(filename, "r");
	if (fp != NULL) {
	    /* Go to the end of the file. */
	    if (fseek(fp, 0L, SEEK_END) == 0) {
	        /* Get the size of the file. */
	        long bufsize = ftell(fp);
	        if (bufsize == -1) { /* Error */ }
	
	        /* Allocate our buffer to that size. */
	        buf = malloc(sizeof(char) * (bufsize + 1));
	
	        /* Go back to the start of the file. */
	        if (fseek(fp, 0L, SEEK_SET) != 0) { /* Error */ }
	
	        /* Read the entire file into memory. */
	        size_t newLen = fread(buf, sizeof(char), bufsize, fp);
	        if (newLen == 0) {
	            fputs("Error reading file", stderr);
	        } else {
	            buf[++newLen] = '\0'; /* Just to be safe. */
	        }
	    }
	    fclose(fp);
		return buf;
	}
	printf("Error reading in file %s\n", filename);
	return NULL;
}
int main(int argc, char *argv[])
{
    size_t i;
    char *text, *text2;
    json_t *old, *new;
    json_error_t error, error2;

    text = request("./example_json/simple1.json");
    text2 = request("./example_json/simple2.json");
    if(!text || !text2)
        return 1;

    old = json_loads(text, 0, &error);
    new = json_loads(text2, 0, &error2);
    free(text);
    free(text2);

    if(!old)
    {
        fprintf(stderr, "error: on line %d: %s\n", error.line, error.text);
        return 1;
    }
    if(!new)
    {
        fprintf(stderr, "error: on line %d: %s\n", error2.line, error2.text);
        return 1;
    }

//    printf("BEFORE\n");
//    printf("%s\n", json_dumps(old, JSON_INDENT(2)));
/////////json_object_set(json_object_get(old, "menu"), "lalala", json_integer(777));  //this works.
//
//    //magic diff function
//    json_object_update(old, new);
//    printf("AFTER\n");
//    printf("%s\n", json_dumps(old, JSON_INDENT(2)));

	/* This loops over all of the new json fields.  
	 * Assume drop any fields in the old not in the new  */
    for (i = 0; i < json_object_size(new); i++) {

  
        /* JSON container: object */
		if (json_is_object(new)) {
			//print_object(new);
			diff_objects(old, new, NULL);
		} 
        ///* JSON container: array */
        else if (json_is_array(new)) {
			/* TODO: for now, just going to process the FIRST element of the
			   array.  I'm not sure yet what our stated assumptions will be.
			   Currently I'm assuming that all array elements are identical,
			   and that the number of array elements does not matter. */

			/* get and process the head array element */
			// TODO this code not tested
			//print_object(json_array_get(new,  0));
			diff_objects(json_array_get(old,  0), json_array_get(new,  0), NULL);
        
		}

		else {
			printf("ERROR. Outermost object must be a container (array or object.)\n");
			return -1;
		}
	}

//    printf("AFTER\n");
//    printf("%s\n", json_dumps(old, JSON_INDENT(2)));
    return 0;
}
