package simblock.transaction;

/**
 * Simple Transaction class for prototype simulation.
 */
public class Transaction {
  private static int counter = 0;  // auto-increment for tx-id
  private final int id;
  private final int senderId;
  private final int receiverId;
  private final double amount;

  public Transaction(int senderId, int receiverId, double amount) {
    this.id = ++counter;
    this.senderId = senderId;
    this.receiverId = receiverId;
    this.amount = amount;
  }

  public int getId() {
    return id;
  }

  public int getSenderId() {
    return senderId;
  }

  public int getReceiverId() {
    return receiverId;
  }

  public double getAmount() {
    return amount;
  }

  @Override
  public String toString() {
    return "tx-" + id;
  }
}
