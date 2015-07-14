require 'rubygems'
gem 'amico', '= 1.2.0'
require 'amico'
Amico.configure do |configuration|
  configuration.redis = Redis.new
  configuration.namespace = 'amico'
  configuration.following_key = 'following'
  configuration.followers_key = 'followers'
  configuration.blocked_key = 'blocked'
  configuration.reciprocated_key = 'reciprocated'
  configuration.pending_key = 'pending'
  configuration.pending_follow = false
  configuration.page_size = 25
end
v1 = ARGV[0]
if v1 == 'kvolve'
  Amico.setns
  puts "SET NAMESPACE"
end
x=0
File.open("wiki-Talk-shuffled1_part1") do |file|
  file.each do |line|
    user = line.split
    Amico.follow(user[0], user[1])
  end
end

