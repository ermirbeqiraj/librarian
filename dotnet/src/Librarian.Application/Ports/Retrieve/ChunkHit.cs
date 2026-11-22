namespace Librarian.Application.Ports.Retrieve;

public sealed record ChunkHit(long ChunkId, long SectionId, long Rank);
