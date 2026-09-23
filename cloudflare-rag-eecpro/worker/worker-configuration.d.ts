interface Env {
  AI: Ai;
  VECTOR_INDEX: VectorizeIndex;
  /**
   * Bearer token for the write endpoint. Declared optional because a
   * Worker CAN be deployed without the secret bound - but checkAuth now
   * refuses every write when it is missing rather than waving them through,
   * so an unset value disables writes instead of opening them.
   */
  WORKER_API_KEY?: string;
}
