s = "{   \"menu\": {   \"id\": 1,   \"live\": true,   \"deleteme\": true,   \"pointer\": null,   \"value\":  \"File\",   \"popup\": {   \"menuitem\": [  {   \"value\":  \"New\",   \"onclick\":  \"CreateNewDoc()\"  },  {   \"value\":  \"Open\",   \"onclick\":  \"OpenDoc()\"  },  {   \"value\":  \"Close\",   \"onclick\":  \"CloseDoc()\"  }  ]  }  },   \"soup\": {   \"delme\": 9,   \"dontmodmes\": 4  } }"
f= open("data.txt", 'w')
i=1
for x in range(1, 100):
     s = s.replace("id\": "+str(i), "id\": "+str(i+1))
     if (x % 3 == 0):
         t = s.replace("CreateNewDoc", "EditExisting")
         t = t.replace("New", "Edit")
         t = t.replace("true", "false")
         f.write(t + "\n")
     else:
         f.write(s + "\n")
     i+=1

