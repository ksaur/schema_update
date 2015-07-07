This code says it's for .5 -> .6.  However, we're actually going to do .5 -> .7 because there was a bug in the commit for .6 and it was immediately replaced by .7, so version .6 is not a functional version.
(http://git.steve.org.uk/skx/redisfs/commits/release-0.7)

The v0v6 code is used in the "eager" migration (non-lazy)...it doesn't use any
versions so that it is the same as normal redis.  it uses versions during the
eager migration only, then goes back to not having any versioning.
