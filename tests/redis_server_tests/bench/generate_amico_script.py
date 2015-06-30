

fin = open("unique_twitter.txt", "r")
aout = open("amico_script.rb", "w")

aout.write("require 'rubygems'\ngem 'amico', '= 1.2.0'\nrequire 'amico'\nAmico.configure do |configuration|\n  configuration.redis = Redis.new\n  configuration.namespace = 'amico'\n  configuration.following_key = 'following'\n  configuration.followers_key = 'followers'\n  configuration.blocked_key = 'blocked'\n  configuration.reciprocated_key = 'reciprocated'\n  configuration.pending_key = 'pending'\n  configuration.pending_follow = false\n  configuration.page_size = 25\nend\nAmico.setns\n")

i=0
for line in fin:
   s = line.split( )
   aout.write("Amico.follow("+s[0]+", "+s[1]+")\n")
   i = i + 1
   if (i%17 == 0):
      aout.write("Amico.follower?("+s[1]+", "+s[0]+")\n")
   if (i%11 == 0):
      aout.write("Amico.following("+s[1]+")\n")
   if (i%13 == 0):
      aout.write("Amico.reciprocated?("+s[1]+", "+s[0]+")\n")
   if (i%19 == 0):
       aout.write("Amico.following_count("+s[1]+")\n")
   if (i%7 == 0):
       aout.write("Amico.followers("+s[0]+")\n")



