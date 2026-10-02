# Server boundary examples

Bad: a client form posts `documentId` and `title` to an action that writes the
record because a protected page already checked project access.

Better: the action parses the title, gets the current principal, verifies
write access for that `documentId`, then writes or returns a field error. A test
asserts that an unauthorized user cannot mutate the document by calling the action
directly.

Bad: a shared cached loader returns account-specific data by URL alone.

Better: keep the loader uncached until the chosen Next.js version's cache
contract, authorization scope and invalidation path are explicit. Where public
data may be cached, name the freshness requirement and test stale behavior at
the level the app owns.
