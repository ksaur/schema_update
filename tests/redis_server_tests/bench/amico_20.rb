require 'rubygems'
gem 'amico', '= 2.0.0'
require 'amico'
Amico.configure do |configuration|
  configuration.redis = Redis.new
  configuration.namespace = 'amico'
  configuration.following_key = 'following'
  configuration.followers_key = 'followers'
  configuration.blocked_key = 'blocked'
  configuration.reciprocated_key = 'reciprocated'
  configuration.pending_key = 'pending'
  configuration.default_scope_key = 'default'
  configuration.pending_follow = false
  configuration.page_size = 25
end
v1 = ARGV[0]
if v1 == 'kvolve'
  Amico.setns
  puts "SET NAMESPACE"
end
x=0
File.open("unique_twitter_shuffled_2") do |file|
  file.each do |line|
    user = line.split
    Amico.follow(user[0], user[1])
    if ((x) % 4) == 0
      Amico.follower?(user[1], user[0])
    elsif ((x+1) % 4) == 0
      Amico.following(user[0])
    elsif ((x+2) % 4) == 0
      Amico.reciprocated?(user[1], user[0])
    elsif ((x+3) % 4) == 0
      Amico.following_count(user[1])
    end
    x = x +1
  end
end

