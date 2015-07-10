import random

fin = open("unique_twitter.txt", "r")
aout = open("amico_script.rb", "w")

aout.write("require 'rubygems'\ngem 'amico', '= 1.2.0'\nrequire 'amico'\nAmico.configure do |configuration|\n  configuration.redis = Redis.new\n  configuration.namespace = 'amico'\n  configuration.following_key = 'following'\n  configuration.followers_key = 'followers'\n  configuration.blocked_key = 'blocked'\n  configuration.reciprocated_key = 'reciprocated'\n  configuration.pending_key = 'pending'\n  configuration.pending_follow = false\n  configuration.page_size = 25\nend\nAmico.setns\n")

i=0
cmds = set()
for line in fin:
   s = line.split( )
   cmds.add("Amico.follow("+s[0]+", "+s[1]+")\n")
   i = i + 1
   if (i%2 == 0):
      cmds.add("Amico.follower?("+s[1]+", "+s[0]+")\n")
      #aout.write("Amico.follower?("+s[1]+", "+s[0]+")\n")
   if (i%3 == 0):
      cmds.add("Amico.following("+s[1]+")\n")
      #aout.write("Amico.following("+s[1]+")\n")
   if (i%4 == 0):
      cmds.add("Amico.reciprocated?("+s[1]+", "+s[0]+")\n")
      #aout.write("Amico.reciprocated?("+s[1]+", "+s[0]+")\n")
   if (i%5 == 0):
      cmds.add("Amico.following_count("+s[1]+")\n")
      #aout.write("Amico.following_count("+s[1]+")\n")
   if (i%6 == 0):
      cmds.add("Amico.followers("+s[0]+")\n")
      #aout.write("Amico.followers("+s[0]+")\n")

while cmds:
   w = random.sample(cmds,100)
   for y in w:
      aout.write(y)
      cmds.remove(y)



