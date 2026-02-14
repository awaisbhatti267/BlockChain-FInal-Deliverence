/*
 * Copyright 2019 Distributed Systems Group
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
 * either express or implied.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 */

package simblock.simulator;

import static simblock.settings.SimulationConfiguration.*;
import static simblock.simulator.Network.getDegreeDistribution;
import static simblock.simulator.Network.getRegionDistribution;
import static simblock.simulator.Network.printRegion;
import static simblock.simulator.Simulator.*;
import static simblock.simulator.Timer.*;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.net.HttpURLConnection;
import java.io.OutputStream;
import java.net.URL;

import simblock.block.Block;
import simblock.node.Node;
import simblock.task.AbstractMintingTask;
import simblock.transaction.Transaction;

/** The type Main represents the entry point. */
public class Main {
  public static Random random = new Random(10);
  public static long simulationTime = 0;
  public static URI CONF_FILE_URI;
  public static URI OUT_FILE_URI;

  static {
    try {
      CONF_FILE_URI = ClassLoader.getSystemResource("simulator.conf").toURI();
      OUT_FILE_URI = CONF_FILE_URI.resolve(new URI("../output/"));
    } catch (URISyntaxException e) {
      e.printStackTrace();
    }
  }

  public static PrintWriter OUT_JSON_FILE;
  public static PrintWriter STATIC_JSON_FILE;

  static {
    try {
      OUT_JSON_FILE = new PrintWriter(
          new BufferedWriter(new FileWriter(new File(OUT_FILE_URI.resolve("./output.json")))));
      STATIC_JSON_FILE = new PrintWriter(
          new BufferedWriter(new FileWriter(new File(OUT_FILE_URI.resolve("./static.json")))));
    } catch (IOException e) {
      e.printStackTrace();
    }
  }

  public static void main(String[] args) {
    final long start = System.currentTimeMillis();
    setTargetInterval(INTERVAL);

    OUT_JSON_FILE.print("[");
    OUT_JSON_FILE.flush();

    // Log regions
    printRegion();

    // Setup network
    constructNetworkWithAllNodes(NUM_OF_NODES);

    // Generate some example transactions
    generateInitialTransactions();

    int currentBlockHeight = 1;

    while (getTask() != null) {
      if (getTask() instanceof AbstractMintingTask) {
        AbstractMintingTask task = (AbstractMintingTask) getTask();
        if (task.getParent().getHeight() == currentBlockHeight) {
          currentBlockHeight++;
        }
        if (currentBlockHeight > END_BLOCK_HEIGHT) {
          break;
        }
        if (currentBlockHeight % 100 == 0 || currentBlockHeight == 2) {
          writeGraph(currentBlockHeight);
        }

        // Log mined block
        logBlock(task.getParent());
      }
      runTask();
    }

    printAllPropagation();

    Set<Block> blocks = new HashSet<>();
    Block block = getSimulatedNodes().get(0).getBlock();
    while (block.getParent() != null) {
      blocks.add(block);
      block = block.getParent();
    }

    Set<Block> orphans = new HashSet<>();
    int averageOrphansSize = 0;
    for (Node node : getSimulatedNodes()) {
      orphans.addAll(node.getOrphans());
      averageOrphansSize += node.getOrphans().size();
    }
    averageOrphansSize = averageOrphansSize / getSimulatedNodes().size();
    blocks.addAll(orphans);

    ArrayList<Block> blockList = new ArrayList<>(blocks);
    blockList.sort(
        (a, b) -> {
          int order = Long.signum(a.getTime() - b.getTime());
          if (order != 0)
            return order;
          return System.identityHashCode(a) - System.identityHashCode(b);
        });

    try {
      FileWriter fw = new FileWriter(new File(OUT_FILE_URI.resolve("./blockList.txt")), false);
      PrintWriter pw = new PrintWriter(new BufferedWriter(fw));

      for (Block b : blockList) {
        if (!orphans.contains(b)) {
          pw.println("OnChain : " + b.getHeight() + " : " + b);
        } else {
          pw.println("Orphan : " + b.getHeight() + " : " + b);
        }
      }
      pw.close();
    } catch (IOException ex) {
      ex.printStackTrace();
    }

    OUT_JSON_FILE.print("{");
    OUT_JSON_FILE.print("\"kind\":\"simulation-end\",");
    OUT_JSON_FILE.print("\"content\":{");
    OUT_JSON_FILE.print("\"timestamp\":" + getCurrentTime());
    OUT_JSON_FILE.print("}");
    OUT_JSON_FILE.print("}");
    OUT_JSON_FILE.print("]");
    OUT_JSON_FILE.close();

    long end = System.currentTimeMillis();
    simulationTime += end - start;
    System.out.println(simulationTime);
  }

  // -------------------------
  // Helpers for Transactions / Blocks
  // -------------------------

  private static void generateInitialTransactions() {
    for (int i = 0; i < 10; i++) {
      int sender = random.nextInt(NUM_OF_NODES) + 1;
      int receiver = random.nextInt(NUM_OF_NODES) + 1;
      double amount = random.nextInt(100) + 1;
      Transaction tx = new Transaction(sender, receiver, amount);

      String txJsonObj = "{"
          + "\"kind\":\"add-tx\","
          + "\"content\":{"
          + "\"timestamp\":" + getCurrentTime() + ","
          + "\"tx-id\":\"" + tx.getId() + "\","
          + "\"sender\":" + sender + ","
          + "\"receiver\":" + receiver + ","
          + "\"amount\":" + amount
          + "}"
          + "}";

      OUT_JSON_FILE.print(txJsonObj + ",");
      OUT_JSON_FILE.flush();

      postToFlaskJson(txJsonObj);
    }
  }

  private static void logBlock(Block block) {
    String blockJsonObj = "{"
        + "\"kind\":\"add-block\","
        + "\"content\":{"
        + "\"timestamp\":" + block.getTime() + ","
        + "\"block-id\":\"" + block + "\","
        + "\"height\":" + block.getHeight() + ","
        + "\"miner-id\":" + block.getMinter().getNodeID() + ","
        + "\"parent-id\":\"" + block.getParent() + "\""
        + "}"
        + "}";

    OUT_JSON_FILE.print(blockJsonObj + ",");
    OUT_JSON_FILE.flush();

    postToFlaskJson(blockJsonObj);
  }

  // Attack logging helper
  public static void logAttack(String message) {
    String safe = message.replace("\"", "\\\"");
    OUT_JSON_FILE.print("{");
    OUT_JSON_FILE.print("\"kind\":\"attack-log\",");
    OUT_JSON_FILE.print("\"content\":{");
    OUT_JSON_FILE.print("\"timestamp\":" + getCurrentTime() + ",");
    OUT_JSON_FILE.print("\"message\":\"" + safe + "\"");
    OUT_JSON_FILE.print("}},");
    OUT_JSON_FILE.flush();

    System.out.println("[ATTACK-LOG] " + message);

    postToFlaskJson("{\"kind\":\"attack-log\",\"content\":{\"timestamp\":" + getCurrentTime()
        + ",\"message\":\"" + safe + "\"}}");
  }

  // -------------------------
  // Forwarder to Flask
  // -------------------------
  public static void postToFlaskJson(String jsonObjectString) {
    try {
      URL url = new URL("http://127.0.0.1:5001/simblock_ingest");
      HttpURLConnection conn = (HttpURLConnection) url.openConnection();
      conn.setDoOutput(true);
      conn.setRequestMethod("POST");
      conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");

      byte[] out = jsonObjectString.trim().getBytes("UTF-8");
      conn.setFixedLengthStreamingMode(out.length);
      conn.connect();
      OutputStream os = conn.getOutputStream();
      os.write(out);
      os.flush();
      os.close();

      conn.getResponseCode();
      conn.disconnect();
    } catch (Exception e) {
      System.err.println("[WARN] Could not forward JSON to Flask: " + e.getMessage());
    }
  }

  // -------------------------
  // Existing Helpers (Unchanged)
  // -------------------------
  public static ArrayList<Integer> makeRandomListFollowDistribution(double[] distribution, boolean facum) {
    ArrayList<Integer> list = new ArrayList<>();
    int index = 0;

    if (facum) {
      for (; index < distribution.length; index++) {
        while (list.size() <= NUM_OF_NODES * distribution[index]) {
          list.add(index);
        }
      }
      while (list.size() < NUM_OF_NODES) {
        list.add(index);
      }
    } else {
      double acumulative = 0.0;
      for (; index < distribution.length; index++) {
        acumulative += distribution[index];
        while (list.size() <= NUM_OF_NODES * acumulative) {
          list.add(index);
        }
      }
      while (list.size() < NUM_OF_NODES) {
        list.add(index);
      }
    }

    Collections.shuffle(list, random);
    return list;
  }

  public static ArrayList<Boolean> makeRandomList(float rate) {
    ArrayList<Boolean> list = new ArrayList<Boolean>();
    for (int i = 0; i < NUM_OF_NODES; i++) {
      list.add(i < NUM_OF_NODES * rate);
    }
    Collections.shuffle(list, random);
    return list;
  }

  public static long genMiningPower() {
    double r = random.nextGaussian();
    return Math.max((long) (r * STDEV_OF_MINING_POWER + AVERAGE_MINING_POWER), 1);
  }

  public static Node getGenesisMinter() {
    long totalMiningPower = 0;
    for (Node node : getSimulatedNodes()) {
      totalMiningPower += node.getMiningPower();
    }

    long randomValue = (long) (random.nextDouble() * totalMiningPower);
    long cumulativeMiningPower = 0;

    for (Node node : getSimulatedNodes()) {
      cumulativeMiningPower += node.getMiningPower();
      if (randomValue < cumulativeMiningPower) {
        return node;
      }
    }
    return null;
  }

  public static void constructNetworkWithAllNodes(int numNodes) {
    double[] regionDistribution = getRegionDistribution();
    List<Integer> regionList = makeRandomListFollowDistribution(regionDistribution, false);

    double[] degreeDistribution = getDegreeDistribution();
    List<Integer> degreeList = makeRandomListFollowDistribution(degreeDistribution, true);

    List<Boolean> useCBRNodes = makeRandomList(CBR_USAGE_RATE);
    List<Boolean> churnNodes = makeRandomList(CHURN_NODE_RATE);

    long attackerPowerUplift = Math
        .max((long) (AVERAGE_MINING_POWER * ATTACKER_HASH_POWER_SHARE * Math.max(1, NUM_OF_NODES)), 1L);

    for (int id = 1; id <= numNodes; id++) {
      long miningPower = genMiningPower();
      Node node;

      if (ENABLE_ATTACKER && id <= NUM_ATTACKER_NODES) {
        long attackerPower = miningPower + attackerPowerUplift;
        node = new Node(
            id,
            degreeList.get(id - 1) + 1,
            regionList.get(id - 1),
            attackerPower,
            TABLE,
            ALGO,
            useCBRNodes.get(id - 1),
            churnNodes.get(id - 1));
        addNode(node);
        System.out.println("[ATTACK] Attacker node created: " + id + " (power=" + attackerPower + ")");
        logAttack("Attacker node created: " + id + " with mining power " + attackerPower);
      } else {
        node = new Node(
            id,
            degreeList.get(id - 1) + 1,
            regionList.get(id - 1),
            miningPower,
            TABLE,
            ALGO,
            useCBRNodes.get(id - 1),
            churnNodes.get(id - 1));
        addNode(node);
      }

      OUT_JSON_FILE.print("{");
      OUT_JSON_FILE.print("\"kind\":\"add-node\",");
      OUT_JSON_FILE.print("\"content\":{");
      OUT_JSON_FILE.print("\"timestamp\":0,");
      OUT_JSON_FILE.print("\"node-id\":" + id + ",");
      OUT_JSON_FILE.print("\"region-id\":" + regionList.get(id - 1));
      OUT_JSON_FILE.print("}},");
      OUT_JSON_FILE.flush();
    }

    for (Node node : getSimulatedNodes()) {
      node.joinNetwork();
    }

    getGenesisMinter().genesisBlock();
  }

  public static void writeGraph(int blockHeight) {
    try {
      FileWriter fw = new FileWriter(new File(OUT_FILE_URI.resolve("./graph/" + blockHeight + ".txt")), false);
      PrintWriter pw = new PrintWriter(new BufferedWriter(fw));

      for (int index = 1; index <= getSimulatedNodes().size(); index++) {
        Node node = getSimulatedNodes().get(index - 1);
        for (int i = 0; i < node.getNeighbors().size(); i++) {
          Node neighbor = node.getNeighbors().get(i);
          pw.println(node.getNodeID() + " " + neighbor.getNodeID());
        }
      }
      pw.close();
    } catch (IOException ex) {
      ex.printStackTrace();
    }
  }
}
