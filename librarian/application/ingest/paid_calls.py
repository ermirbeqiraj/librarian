"""The cap on the paid model calls one document may make. Each paid adapter spends one per
request it sends, its own retries included."""


class PaidCallsSpent(Exception):
    pass


class PaidCalls:
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.count = 0

    def spend(self) -> None:
        """Stops the request past the cap."""
        if self.count == self.cap:
            raise PaidCallsSpent(f"{self.cap} paid calls spent, the cap for one document")
        self.count += 1
