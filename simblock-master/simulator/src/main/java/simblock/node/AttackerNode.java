//AttackerNode.java


package simblock.node;

import simblock.block.Block;
import simblock.simulator.Main;
import simblock.transaction.Transaction;
import simblock.node.Node;




import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/**
 * AttackerNode - merged implementation that:
 *  - supports SELFISH mining (withhold private chain) and
 *  - attempts DOUBLE_SPEND (adds a conflicting tx to a mined block if block exposes tx list).
 *
 * This version avoids compile-time dependency on exact Node/Block signatures by using reflection
 * when calling superclass callbacks or working with Block transaction lists.
 *
 * Note: This is a prototype. Adjust behavior to match your Node/Block API if you know exact names.
 */
public class AttackerNode extends Node {

  private Block privateHead;               // tip of private chain
  private final List<Block> privateChain;  // withheld blocks
  private Transaction doubleSpendTx;       // fake tx for double spend

  public AttackerNode(
      int nodeID,
      int numConnections,
      int region,
      long miningPower,
      String table,
      String algo) {

    // Use the same constructor signature as your Node class (common pattern).
    super(nodeID, numConnections, region, miningPower, table, algo, false, false);

    this.privateHead = null;
    this.privateChain = new ArrayList<>();
    this.doubleSpendTx = null;

    safeLog("[ATTACK] Attacker node initialized: " + nodeID);
  }

  // ------------------------
  // Mining callback entry points
  // ------------------------
  // We provide both minedBlock and onMined style entries — do NOT annotate @Override to avoid
  // compile-time mismatch with different SimBlock versions. We call handleMined() so either
  // user code invoking a specific signature will trigger the same behavior.

  public void minedBlock(Block block) {
    handleMined(block);
  }

  public void onMined(Block block) {
    handleMined(block);
  }

  // Centralized mined handling
  private void handleMined(Block block) {
    String strat = getAttackStrategy();

    if ("SELFISH".equals(strat)) {
      // Withhold block: add to private chain and don't publish immediately
      this.privateHead = block;
      this.privateChain.add(block);
      safeLog("[ATTACK] Attacker mined block " + block.getHeight() + " but withheld it (selfish).");
      // don't publish now
    } else if ("DOUBLE_SPEND".equals(strat)) {
      // Create double spend tx if not already
      if (this.doubleSpendTx == null) {
        try {
          // receiver id 999 used as example — adapt to your scenario
          this.doubleSpendTx = new Transaction(this.getNodeID(), 999, 100.0);
          safeLog("[ATTACK] Attacker created double-spend tx: " + this.doubleSpendTx.getId());
        } catch (Throwable t) {
          // If Transaction constructor is different, skip creation
          safeLog("[ATTACK] Could not create Transaction object for double-spend: " + t.getMessage());
        }
      }

      // Try to append the tx into the block transaction list, if accessible
      if (this.doubleSpendTx != null) {
        try {
          // Try common accessor names via reflection
          Method getTxs = null;
          try {
            getTxs = block.getClass().getMethod("getTxList"); // some versions
          } catch (NoSuchMethodException nsm) {
            try {
              getTxs = block.getClass().getMethod("getTransactions"); // alternate
            } catch (NoSuchMethodException ex) {
              getTxs = null;
            }
          }

          if (getTxs != null) {
            Object txListObj = getTxs.invoke(block);
            if (txListObj instanceof List) {
              @SuppressWarnings("unchecked")
              List<Object> txList = (List<Object>) txListObj;
              txList.add(this.doubleSpendTx);
              safeLog("[ATTACK] Injected double-spend tx into block " + block.getHeight());
            }
          }
        } catch (Throwable t) {
          safeLog("[ATTACK] Unable to inject tx into block (ignored): " + t.getMessage());
        }
      }

      // Publish the block (attempt to call any known super callback via reflection)
      boolean published = invokeSuperCallbackIfExists("onMined", Block.class, block);
      if (!published) {
        published = invokeSuperCallbackIfExists("minedBlock", Block.class, block);
      }
      if (!published) {
        // If no super publish callback exists, log only
        safeLog("[ATTACK] Attacker broadcast block with double-spend at height " + block.getHeight() + " (no super callback found).");
      } else {
        safeLog("[ATTACK] Attacker broadcast block with double-spend at height " + block.getHeight());
      }
    } else {
      // Default honest behaviour: try to call super method if available
      boolean invoked = invokeSuperCallbackIfExists("onMined", Block.class, block);
      if (!invoked) {
        invokeSuperCallbackIfExists("minedBlock", Block.class, block);
      }
    }
  }

  // ------------------------
  // Receiving blocks
  // ------------------------
  // Provide both possible signatures: (Block) and (Block, Node)
  public void receiveBlock(Block block) {
    handleReceived(block, null);
  }

  public void receiveBlock(Block block, Node from) {
    handleReceived(block, from);
  }

  private void handleReceived(Block block, Node from) {
    String strat = getAttackStrategy();

    if ("SELFISH".equals(strat)) {
      if (this.privateHead != null && this.privateHead.getHeight() <= block.getHeight()) {
        safeLog("[ATTACK] Honest block caught up → attacker releasing private chain.");
        // Try to publish private chain blocks via super callbacks
        for (Block b : new ArrayList<>(this.privateChain)) {
          boolean published = invokeSuperCallbackIfExists("onMined", Block.class, b);
          if (!published) {
            published = invokeSuperCallbackIfExists("minedBlock", Block.class, b);
          }
          // best-effort; ignore if cannot publish
        }
        this.privateChain.clear();
        this.privateHead = null;
      }
    }

    // After attack-specific logic, attempt standard processing by calling super.receiveBlock if present.
    boolean invoked = invokeSuperCallbackIfExists("receiveBlock", Block.class, block);
    if (!invoked) {
      // Try signature receiveBlock(Block, Node)
      invoked = invokeSuperCallbackIfExists("receiveBlock", Block.class, Node.class, block, from);
    }
    if (!invoked) {
      // no super processing available; log and continue
      safeLog("[ATTACK] No super.receiveBlock found; attacker processed block height " + block.getHeight());
    }
  }

  // ------------------------
  // Utilities: reflection helpers and logging
  // ------------------------

  // Attempt to call a method declared in Node (or its superclass) if it exists.
  // Returns true if invocation succeeded (method found & invoked), false otherwise.
  private boolean invokeSuperCallbackIfExists(String methodName, Class<?> paramType, Object param) {
    try {
      Method m = findMethodInHierarchy(this.getClass().getSuperclass(), methodName, paramType);
      if (m != null) {
        m.setAccessible(true);
        m.invoke(this, param);
        return true;
      }
    } catch (Throwable t) {
      // ignore and return false
    }
    return false;
  }

  // Overload to support two-arg invocations (Block, Node)
  private boolean invokeSuperCallbackIfExists(String methodName, Class<?> p1, Class<?> p2, Object arg1, Object arg2) {
    try {
      Method m = findMethodInHierarchy(this.getClass().getSuperclass(), methodName, p1, p2);
      if (m != null) {
        m.setAccessible(true);
        m.invoke(this, arg1, arg2);
        return true;
      }
    } catch (Throwable t) {
      // ignore and return false
    }
    return false;
  }

  // Searches class hierarchy for a method with given name and parameter types
  private Method findMethodInHierarchy(Class<?> start, String name, Class<?>... paramTypes) {
    Class<?> c = start;
    while (c != null) {
      try {
        Method m = c.getDeclaredMethod(name, paramTypes);
        return m;
      } catch (NoSuchMethodException e) {
        // try parent
        c = c.getSuperclass();
      }
    }
    return null;
  }

  // Read ATTACK_STRATEGY field from SimulationConfiguration if exists; returns upper-case or empty string.
  private String getAttackStrategy() {
    try {
      Class<?> conf = Class.forName("simblock.settings.SimulationConfiguration");
      Field f = null;
      try {
        f = conf.getField("ATTACK_STRATEGY"); // public field
      } catch (NoSuchFieldException nsf) {
        try {
          f = conf.getDeclaredField("ATTACK_STRATEGY"); // maybe non-public
          f.setAccessible(true);
        } catch (NoSuchFieldException ex) {
          f = null;
        }
      }
      if (f != null) {
        Object val = f.get(null);
        if (val != null) {
          return val.toString().trim().toUpperCase();
        }
      }
    } catch (Throwable t) {
      // ignore
    }
    return "";
  }

  // Safe logging: prefer Main.logAttack if available, else System.out
  private void safeLog(String msg) {
    try {
      Method ml = Main.class.getMethod("logAttack", String.class);
      ml.invoke(null, msg);
    } catch (Throwable t) {
      System.out.println(msg);
    }
  }

  // Optional manual release API
  public void releasePrivateChain() {
    if (!this.privateChain.isEmpty()) {
      safeLog("[ATTACK] Manual release of private chain by attacker.");
      for (Block b : new ArrayList<>(this.privateChain)) {
        invokeSuperCallbackIfExists("onMined", Block.class, b);
        invokeSuperCallbackIfExists("minedBlock", Block.class, b);
      }
      this.privateChain.clear();
      this.privateHead = null;
    }
  }
}
