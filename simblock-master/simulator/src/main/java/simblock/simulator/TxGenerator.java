package simblock.simulator;

import simblock.simulator.Timer;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Transaction generator for SimBlock experiments.
 *
 * Modes:
 *   - FIXED: every tx uses the same fixed amount
 *   - ROUND_ROBIN: senders are chosen round-robin with fixed amount
 *   - BALANCE_AWARE: maintains balances and ensures senders don’t overspend
 *
 * Produces JSON strings consistent with SimBlock’s output.json format.
 */
public class TxGenerator {

  public enum Mode { FIXED, ROUND_ROBIN, BALANCE_AWARE }

  private final Mode mode;
  private final int fixedAmount;
  private final List<Integer> nodeIds; // list of all node IDs (1..N)
  private final Random rand;
  private final AtomicInteger rrIndex = new AtomicInteger(0);

  // Balance map (only used in BALANCE_AWARE). Keys are node IDs.
  private final Map<Integer, Long> balances = new HashMap<>();

  /**
   * Construct a transaction generator.
   *
   * @param mode generation mode (FIXED, ROUND_ROBIN, BALANCE_AWARE)
   * @param fixedAmount the fixed tx amount to use
   * @param nodeIds list of all participating node IDs
   * @param seed random seed for repeatability
   */
  public TxGenerator(Mode mode, int fixedAmount, List<Integer> nodeIds, long seed) {
    this.mode = mode;
    this.fixedAmount = fixedAmount;
    this.nodeIds = new ArrayList<>(nodeIds);
    this.rand = new Random(seed);

    // Initialize balances for BALANCE_AWARE mode
    for (Integer id : nodeIds) {
      balances.put(id, 1000L); // default 1000 coins each
    }
  }

  /** Set balance for a specific node (only used in BALANCE_AWARE mode). */
  public void setBalance(int nodeId, long amount) {
    balances.put(nodeId, amount);
  }

  /**
   * Generate a new transaction JSON string for output.json
   * Format:
   * {"kind":"create-tx","content":{"timestamp":...,"txid":"...","from":X,"to":Y,"amount":Z}}
   */
  public String createTxJson() {
    int from = chooseSender();
    int to = chooseReceiver(from);
    long amount = chooseAmount(from);

    // update balances if BALANCE_AWARE
    if (mode == Mode.BALANCE_AWARE) {
      long fromBalance = balances.getOrDefault(from, 0L);
      balances.put(from, Math.max(0L, fromBalance - amount));
      balances.put(to, balances.getOrDefault(to, 0L) + amount);
    }

    long ts = getTimestamp();
    String txid = String.format("tx:%d:%d:%d:%d", ts, from, to, amount);

    StringBuilder sb = new StringBuilder();
    sb.append("{");
    sb.append("\"kind\":\"create-tx\",");
    sb.append("\"content\":{");
    sb.append("\"timestamp\":").append(ts).append(",");
    sb.append("\"txid\":\"").append(txid).append("\",");
    sb.append("\"from\":").append(from).append(",");
    sb.append("\"to\":").append(to).append(",");
    sb.append("\"amount\":").append(amount);
    sb.append("}");
    sb.append("},");
    return sb.toString();
  }

  // --- helpers ------------------------------------------------------

  private long getTimestamp() {
    try {
      return Timer.getCurrentTime(); // use SimBlock’s timer if available
    } catch (Throwable t) {
      return System.currentTimeMillis();
    }
  }

  private int chooseSender() {
    if (mode == Mode.ROUND_ROBIN) {
      int idx = rrIndex.getAndIncrement() % nodeIds.size();
      return nodeIds.get(idx);
    } else if (mode == Mode.BALANCE_AWARE) {
      // pick sender with enough balance
      List<Integer> capable = new ArrayList<>();
      for (Map.Entry<Integer, Long> e : balances.entrySet()) {
        if (e.getValue() >= fixedAmount) capable.add(e.getKey());
      }
      if (capable.isEmpty()) {
        return nodeIds.get(rand.nextInt(nodeIds.size()));
      }
      return capable.get(rand.nextInt(capable.size()));
    } else { // FIXED
      return nodeIds.get(rand.nextInt(nodeIds.size()));
    }
  }

  private int chooseReceiver(int from) {
    int to;
    do {
      to = nodeIds.get(rand.nextInt(nodeIds.size()));
    } while (to == from && nodeIds.size() > 1);
    return to;
  }

  private long chooseAmount(int from) {
    if (mode == Mode.FIXED || mode == Mode.ROUND_ROBIN) {
      return fixedAmount;
    } else { // BALANCE_AWARE
      long bal = balances.getOrDefault(from, 0L);
      if (bal <= 0) return 0;
      return Math.min(fixedAmount, bal);
    }
  }
}
