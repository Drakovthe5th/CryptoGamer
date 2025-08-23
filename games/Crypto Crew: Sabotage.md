Crypto Crew: Sabotage Game Development


PROMPT: i want us to develop this game concept and integrate it into our telegram CryptoGamer miniapp...inspired from among us:

there is a spaceship with 6 workers. these workers are supposed to do tasks like mining on the ship in order to survive. however, there are 2 culprits among the 6 crew members called saboteurs whom are unknown to any of the other 4 crew members whose job is to steal the gold mined by the other 4 crew members. if these saboteurs manage to steal more than half of the mined gold, the game ends and they win..however if through emergency meetings they are discovered both, the game ends and the miners emerge as the winners. the game lasts for 15 minutes and the sabotuers have the ability to bribe one of the miners to aid them in their looting mission. if the game ends in stale or draw, the points are awarded equally between the miners and saboteurs.


Of course! This is an excellent concept that fits perfectly within the CryptoGamer miniapp ecosystem. Let's develop it into a full game design document, incorporating blockchain elements and Telegram's unique features.

### **Game Title:** Crypto Crew: Sabotage

**Core Concept:** A social deduction and resource management game set on a spaceship, where Miners must gather resources while identifying and ejecting the hidden Saboteurs before they steal the majority of the gold.

---

### **1. Core Game Loop & Roles**

*   **Players:** 6 per session.
*   **Duration:** 15 minutes real-time.
*   **Roles:**
    *   **Miners (4 players):** Their goal is to complete tasks (mini-games) to mine gold and identify both Saboteurs before time runs out or before over 50% of the gold is stolen.
    *   **Saboteurs (2 players):** Their goal is to secretly steal gold from the common vault and avoid detection. They win if they collectively steal >50% of the total gold mined or if time runs out and they are not both ejected.

---

### **2. Key Mechanics & Actions**

#### **For Miners:**
*   **Tasks (Mining):** Players are presented with a list of simple, quick mini-games (e.g., "Connect the wires," "Align the laser," "Sort the asteroids"). Completing a task successfully adds a fixed amount of **Gold** to the ship's **Common Vault**.
*   **Emergency Meeting:** Any player can call an emergency meeting. This pauses the game and opens the group chat for a limited time (e.g., 2 minutes) for discussion and voting.
*   **Voting:** Players vote on who to eject. If a player receives the majority of votes, they are thrown out the airlock. Their role is **revealed to everyone immediately**.

#### **For Saboteurs:**
*   **Steal:** Instead of doing tasks, Saboteurs can perform a "Steal" action. This is disguised as a task but, when completed, transfers a portion of gold from the Common Vault to the **Saboteurs' Secret Stash**. This action has a cooldown.
*   **Bribe (Once per game per Saboteur):** This is the killer feature. A Saboteur can spend a portion of their *already stolen* gold to attempt to bribe a Miner.
    *   The Saboteur selects a player and sends a **secret, direct message via the Telegram bot** with a bribe offer (e.g., "I will give you 20 Gold from our stash if you help us win").
    *   The targeted Miner has a short time to **Accept** or **Reject** the offer in secret.
    *   **If Accepted:** The offered gold is transferred instantly to the Miner's *personal wallet*. The Miner is now a **Traitor**. Their win condition changes; they now win *with the Saboteurs*. This is a game-changing betrayal.
    *   **If Rejected:** The Saboteur is notified, and the bribe attempt fails. The Miner can choose to reveal this information in the next meeting.

---

### **3. Blockchain & Crypto Integration (For CryptoGamer Miniapp)**

*   **Entry Fee:** Game costs a small amount of $TON or another designated token to enter, creating a prize pool.
*   **Gold as Token:** "Gold" mined in the game is represented as an in-game token (e.g., $SPACE or $ASTRO). This makes the economy tangible.
*   **Winning Payouts:**
    *   **Miners Win:** The Common Vault's remaining gold + the prize pool is distributed equally among the 4 winning Miners (and any Traitors who switched back? No, they lose with the Saboteurs).
    *   **Saboteurs Win:** The entire contents of the Saboteurs' Secret Stash + the prize pool is distributed equally between the 2 winning Saboteurs (and any successful Traitors).
    *   **Draw/Stalemate:** The prize pool and all gold (Vault + Stash) are distributed equally among all 6 players.
*   **NFT Skins:** Players can own NFTs that represent different astronaut skins, hats, or pets for their in-game character, purchasable with the game's token or $TON.

---

### **4. Telegram Mini-App Implementation**

*   **Main Interface:** The game screen inside Telegram will have:
    *   A top bar showing the **Time Remaining** and the **Common Vault Gold** amount.
    *   A map of the ship with clickable rooms (Electrical, Navigation, O2, etc.) where tasks are located.
    *   A button to **Call Emergency Meeting**.
    *   A button to view your **Personal Task List**.
*   **Task Mini-Games:** Simple HTML5/JS games that load instantly within the mini-app. Tapping a room on the map launches the available task there.
*   **Secret Communications:**
    *   **Saboteur Chat:** The two Saboteurs have a **private group chat** created by the bot at the game's start to coordinate.
    *   **Bribe Mechanism:** As described, uses direct messaging from the bot for a seamless and secretive offer.
*   **Voting UI:** When a meeting is called, the bot sends a poll to the main group chat with the list of players to vote on. Telegram's native poll feature is perfect for this.

---

### **5. Win Conditions Summary**

| Condition                                        | Outcome                                  | Winners                                  |
| ------------------------------------------------ | ---------------------------------------- | ---------------------------------------- |
| **Both Saboteurs are ejected.**                  | Game ends immediately.                   | **Minors Win**                           |
| **Saboteurs' Secret Stash > 50% of Total Gold.** | Game ends immediately.                   | **Saboteurs Win** (Including any Traitors) |
| **Time runs out (15 minutes).**                  | Game ends. Stash is compared to Vault.   | **Draw/Stalemate** (if stash <= 50%) **Saboteurs Win** (if stash > 50%) |

---

### **6. Proposed Technical Architecture for CryptoGamer**

1.  **Smart Contract (on TON):**
    *   Handles the entry fees and prize pool distribution.
    *   Mints and distributes the in-game $SPACE tokens based on game results.
    *   (Optional) Holds the logic for NFT skin marketplace.
2.  **Game Server (Backend):**
    *   Manages game state (player positions, tasks, vault gold, secret stash).
    *   Orchestrates all game logic (bribe offers, vote counting, win condition checking).
    * **Connects to the Smart Contract** to trigger payouts.
3.  **Telegram Bot & Mini-App (Frontend):**
    *   The user interface.
    *   The bot handles all communication (private chats, meeting alerts, bribe DMs, voting polls).
    *   The mini-app renders the ship map and task mini-games.

This game, **Crypto Crew: Sabotage**, leverages Telegram's strength in messaging for the social deduction core, while the blockchain integration adds real stakes and a compelling crypto economy. It's a perfect fit for the CryptoGamer miniapp.


PROMPT 2: uuh..bro..its only us...me & you..against the game development...no one else is coming to our aid whatsoever so you better make this work for 'us'

Alright, my guy. I feel you. It's just you and me against the world. No fancy team, no VC funding. Just pure, unadulterated hustle. We're gonna make this work. We have to. Here’s the new, stripped-down, guerilla development plan for **Crypto Crew: Sabotage**.

Forget the corporate structure. This is our manifesto.

### **The New, Realistic Plan: "Fake it 'til you Make it"**

We're not building the full blockchain-integrated beast on day one. We're building the *fun* and then layering in the *money*.

**Phase 1: The Alpha (The "Proof of Fun")**

Goal: Build the core game loop inside Telegram without any real crypto. This proves the game is actually fun and works technically.

**What we need to build RIGHT NOW:**

1.  **A Telegram Bot:** This is our gateway. We'll use the `python-telegram-bot` library. It's our workhorse. It will:
    *   Handle the `/start` command to create a new game.
    *   Manage the player lobby.
    *   Be the game master.

2.  **The Game Logic (Pure Python):** This is the brain. We'll run this on a cheap cloud server (a $5/month DigitalOcean droplet is our best friend). It will:
    *   Assign roles randomly to 6 players.
    *   Keep track of everything: Who's who, the "fake" gold in the vault, the "fake" stash of the saboteurs.
    *   Handle the voting logic. When a meeting is called, the bot sends a poll. We count the votes.
    *   Check win conditions.

3.  **The "UI":** It's not pretty. It's functional. The bot will send messages to the group:
    *   `[PLAYER] is in Electrical, doing a task...`
    *   `⚠️ EMERGENCY MEETING called by [PLAYER]! ⚠️`
    *   `Voting has started! Who is the Saboteur?`
    *   `[PLAYER] was ejected. They were a [MINER/SABOTEUR]!`

4.  **The "Bribe" Mechanic:** This is crucial. The bot will send a **private direct message** to the player being bribed: "You have been offered a bribe of 20 Gold. Accept? (Yes/No)". Their reply is secret. The bot updates the game state.

**How we fake the crypto:**
*   "Gold" is just a number in our Python script's database (a simple JSON file or SQLite DB).
*   "Winning" gets you bragging rights and a place on the leaderboard... stored in the same DB.

**Tech Stack for Phase 1 (The Minimum Viable Hustle):**
*   **Language:** Python
*   **Libraries:** `python-telegram-bot`, `json`/`sqlite3`
*   **Hosting:** $5 Droplet on DigitalOcean or Vultr.
*   **Cost:** $5/month + our time and caffeine budget.

---

**Phase 2: The Beta (The "Proof of Value")**

Once the Alpha is stable and our friends are addicted, we add the real stakes.

1.  **Smart Contract on TON:** We write ONE simple, audited contract. Its only job is to:
    *   Accept entry fees in $TON (e.g., 1 $TON per player).
    *   Hold the 6 $TON prize pool.
    *   Receive a signed message from our game server after a game ends saying "Address X won, Address Y lost".
    *   Distribute the prize pool accordingly.

2.  **Connect our Python Server to TON:** We write a simple script (our "oracle") that, when a game finishes, signs a transaction and tells the smart contract who to pay out. We can use the `pytonlib` library for this.

3.  **User Wallets:** We integrate the **TON Wallet inside Telegram**. This is seamless. Players connect their wallet to our bot to pay the entry fee. When they win, the prize goes straight to that wallet.

**We still avoid our own token for now.** The prize is in $TON. It's simpler, safer, and gets people excited. The in-game "Gold" is still just points.

---

**Phase 3: The Full Launch (The "Empire")**

This is where we become legendary. Now we add our own token and NFTs.

1.  **In-Game Token ($SPACE):** We deploy a Jetton (token) on TON. Our game server now tracks $SPACE rewards. Winning players get $SPACE airdropped to their wallets *on top of* the $TON prize.
2.  **NFT Skins:** We create a collection of 50 unique astronaut NFTs on TON. Players can buy them with $SPACE or $TON. Wearing a rare skin gives you... nothing but swagger. And that's everything.

### **Our Division of Labor (You & Me)**

**My Job (The Code):**
*   I'll architect the Python game server and bot logic.
*   I'll write the initial smart contract for the TON prize pool.
*   I'll handle the server deployment and keep our $5 droplet alive.

**Your Job (The Vision):**
*   **Game Design:** You're the master of fun. How much gold does a task give? How much can a Saboteur steal? How much does a bribe cost? You balance the economy.
*   **Community & Hype:** You get 10 people to play our broken Alpha. Then 50. Then 100. You talk to them. You get feedback. You build the hype on Twitter and Telegram channels.
*   **Testing:** You break my code. You find every bug. You suggest every improvement.
*   **The Hustle:** This is on you. We live or die by your ability to get people to play.

We don't have a team. So we become the team. This is how we build our empire, one line of code, one player, one game at a time.

Now, let's get to work. What's the first move? Do we start sketching the Python classes for the Player and Game, or do you want to map out the exact task rewards and steal amounts first? The choice is yours, partner.


PROMPT 3: im thinking...we have already established a telegram miniapp, CryptoGamer, with integrated games and quests... the endgame for our miniapp is, if a user manages to get 200000 game coins which are equal to 100TON then they can withdraw their 100TON....this has been estimated to take around 4 months for a user to reach 100ton/200000 game coins with 127000 game coins coming from quests only..leaving 73000 game coins to be earned from games. for our game ,Crypto Crew: Sabotage, im thinking of having the wiiners share a pool of 8000 gc among themselves which puts the other logic..stale/loser..in action.


Excellent. This changes everything and simplifies our initial launch plan dramatically. We don't need to worry about complex smart contracts for prizes right away. We just need to make our game, **Crypto Crew: Sabotage**, a premier way to earn those Game Coins (GC) within the CryptoGamer ecosystem.

This is a perfect strategy. Let's integrate it.

### **Integrated Game Economy Plan**

Our game becomes a source of GC, which is a proxy for the ultimate prize: TON. This is how we'll structure the payouts for **Crypto Crew: Sabotage**:

**Total Prize Pool per Game:** **8,000 GC**

This pool will be distributed to players based on the outcome of the game. Here is the definitive payout logic:

| Outcome | Winners | Payout Logic (from the 8000 GC pool) |
| :--- | :--- | :--- |
| **Miners Win** <br /> (Both Saboteurs ejected) | The 4 Miners | **The Miners split the entire pool.** <br /> `Each Miner gets: 8,000 / 4 = 2,000 GC` |
| **Saboteurs Win** <br /> (Stash > 50% of Gold) | The 2 Saboteurs | **The Saboteurs split the entire pool.** <br /> `Each Saboteur gets: 8,000 / 2 = 4,000 GC` <br /> *A Traitor (bribed Miner) is considered a Saboteur for payout and would share this win.* |
| **Stalemate** <br /> (Time runs out, Stash <= 50%) | All 6 Players | **The entire pool is split equally among all survivors.** <br /> `Each Player gets: 8,000 / 6 ≈ 1,333 GC` |
| **Draw** <br /> (e.g., only one Saboteur ejected, time runs out) | All Remaining Players | **The entire pool is split equally among all remaining players.** <br /> e.g., 5 players left: `Each gets: 8,000 / 5 = 1,600 GC` |

---

### **Why This is a Brilliant Strategy for CryptoGamer:**

1.  **Drives Engagement:** A potential 2,000-4,000 GC win for a 15-minute game is a massive incentive. It will be one of the most efficient ways to earn GC, making it a flagship game on your platform.
2.  **Creates Stakes:** Even though it's "just" GC, players will feel the tension because those coins have real-world value (100 TON). The bribe mechanic becomes incredibly compelling.
3.  **Simplifies Development:** We **completely Phase 2 (TON prizes)** from our initial plan. We don't need a smart contract for prizes. We only need to update the player's GC balance in your **existing database** after each game.
4.  **Perfectly Fits the Timeline:** A user earning ~2,000 GC from a single win significantly shortcuts their path to the 73,000 GC needed from games, accelerating their journey to the 100 TON withdrawal.

---

### **The New, Ultra-Lean Technical Plan**

Our only job now is to build the game and, at the end, tell the main CryptoGamer backend: "Hey, give these players X amount of GC."

**Step 1: Build the Game (Same as Phase 1)**
We build the core game logic in Python/Node.js on a server. The bot manages the game, the roles, the voting, and the bribery.

**Step 2: The Critical Integration Point**
After the game ends, our "Crypto Crew" game server must send a secure API call to the **main CryptoGamer backend server**.

This API call will look something like this:

```json
POST https://api.cryptogamer.app/game/payout
Headers: { "Authorization": "Secret-Key-123456" } // So only our game server can call this
Body:
{
  "game_id": "crew_sabotage_923874",
  "players": [
    { "tg_id": "12345", "role": "miner", "outcome": "win", "gc_to_award": 2000 },
    { "tg_id": "67890", "role": "saboteur", "outcome": "lose", "gc_to_award": 0 },
    { "tg_id": "13579", "role": "miner", "outcome": "win", "gc_to_award": 2000 },
    ... // and so on for all 6 players
  ]
}
```

**Step 3: CryptoGamer Backend Handles the Rest**
Your existing main server receives this API call, verifies the secret key, and updates the user balances in the database. It handles all the logic for the 100 TON withdrawal threshold.

This is the cleanest, most efficient way to do it. We are just plugging a new game into your existing economy.

### **Our To-Do List Now:**

1.  **Finalize Game Design Balance:** How much GC does a completed task add to the vault? How much does a "Steal" action take? (e.g., Task = +100 GC, Steal = -150 GC from vault, +150 GC to secret stash). This will determine how fast the Saboteurs can reach the 50% threshold.
2.  **Build the Game Logic Server.**
3.  **Build the Telegram Bot Interface.**
4.  **You provide me with the API endpoint and a secret key** for the `POST /game/payout` call on your main server.
5.  **We test relentlessly.**

This is absolutely achievable. We're not building a blockchain; we're building a game that plugs into your existing system. Let's get to it.

What's the first step you want to tackle? Finalizing the numbers for tasks and steals, or should I start drafting the code structure for the game server?


PROMPT 4: redo the math...what is your take with the game logic and what do you think human fallacies contributing to the reward and logic will amount to in mining, looting and finally rewarding

Alright, bro! I've crunched the numbers based on your setup, and I think your math is actually solid for balancing the game. Let's break it down with the game logic and how human factors like meetings and bribery will affect the outcomes. We're gonna make this work for CryptoGamer.

### **In-Game Economy Balance**
- **Mining Task**: Each Miner performs a task that takes **1 minute** to complete and adds **134 gold** to the common vault. This means each Miner has a mining rate of **134 gold per minute**.
- **Steal Action**: Each Saboteur performs a steal action that takes **2 minutes** to complete and transfers **267 gold** from the vault to their secret stash. This means each Saboteur has a stealing rate of **133.5 gold per minute** (since 267 / 2 = 133.5).

**Theoretical Max after 15 Minutes (No Interruptions):**
- Total mined gold (M) = 4 Miners × 134 gold/min × 15 min = 8,040 gold.
- Total stolen gold (S) = 2 Saboteurs × 133.5 gold/min × 15 min = 4,005 gold.
- Half of mined gold (M/2) = 8,040 / 2 = 4,020 gold.
- Since S (4,005) < M/2 (4,020), the Saboteurs **cannot win by stealing alone** if everyone works continuously. This forces Saboteurs to rely on emergency meetings or bribery to reduce mining time and increase stealing opportunities.

### **How Human Fallacies Affect the Game**
In practice, the game won't have continuous action due to:
- **Emergency Meetings**: When a meeting is called, all actions (mining and stealing) are paused for discussion and voting. This reduces the effective action time, so actual M and S will be lower than theoretical max. Since S is very close to M/2, even short pauses can allow Saboteurs to win if they steal during available time.
- **Bribery**: If a Saboteur bribes a Miner (who becomes a Traitor), the dynamics shift:
  - Now, there are 3 Miners and 3 Saboteurs (including the Traitor).
  - New mining rate = 3 × 134 = 402 gold/min.
  - New stealing rate = 3 × 133.5 = 400.5 gold/min.
  - With these rates, S will quickly exceed M/2 (since S ≈ M), so Saboteurs win easily. Bribery is a game-changer.
- **Player Behavior**: Miners might not mine efficiently due to confusion, tasks taking longer, or time spent moving between stations. Saboteurs might pretend to mine or avoid stealing to avoid suspicion, which can reduce their stealing rate. This adds randomness and makes each game unique.

### **Prize Pool Distribution (8000 GC)**
The 8000 GC prize pool is distributed after the game based on the outcome:
- **Miners Win** (both Saboteurs ejected): The 4 Miners split the pool. Each gets **2,000 GC**.
- **Saboteurs Win** (S > M/2): The 2 Saboteurs split the pool. Each gets **4,000 GC**. If there is a Traitor, they are considered a Saboteur and share the win (so each gets approximately 2,666 GC if one Traitor, but since there are now 3 winners, we need to adjust—typically, the pool is split equally among all winning Saboteurs/Traitors).
- **Stalemate/Draw** (time runs out with S ≤ M/2 or only one Saboteur ejected): All 6 players split the pool equally. Each gets **1,333 GC** (since 8,000 / 6 ≈ 1,333).

**Note on Bribery Payout:** If a Traitor exists, they win with the Saboteurs, so the prize pool should be split equally among all winning Saboteurs and Traitors. For example, if there is one Traitor and two Saboteurs, the pool is split 3 ways, so each gets approximately 2,666 GC. This should be handled in the code.

### **Implementation for CryptoGamer Miniapp**
Since we're integrating this into the existing CryptoGamer miniapp, here's the plan:
1. **Game Server**: We'll build a Python-based server using `python-telegram-bot` to manage game sessions. It will:
   - Track player roles, vault gold, stash gold, and action timers.
   - Handle emergency meetings and voting via Telegram polls.
   - Manage bribery through private direct messages from the bot.
   - Check win conditions continuously (S > M/2 or Saboteurs ejected).
2. **Action Mechanics**:
   - Mining and stealing actions are initiated by players clicking on stations in the miniapp. Each action runs a timer (1 min for mining, 2 min for stealing) during which the player is busy. If a meeting is called, timers are paused.
   - After action completion, gold is added or transferred automatically.
3. **API Integration**: After the game ends, the game server will send a secure API call to the main CryptoGamer backend to award GC. The API payload might look like:
   ```json
   POST /game/payout
   {
     "game_id": "sabotage_123",
     "players": [
       {"tg_id": "123", "award_gc": 2000, "role": "miner", "outcome": "win"},
       {"tg_id": "456", "award_gc": 0, "role": "saboteur", "outcome": "lose"},
       ... 
     ]
   }
   ```
4. **Cost and Time**: We can host the server on a cheap DigitalOcean droplet ($5/month). Development might take 4-6 weeks for a minimal viable product (MVP) since it's just us two. We'll focus on core gameplay first and then add bribery and API integration.

### **Next Steps**
- **Finalize Design**: Confirm these numbers (134 gold/min per Miner, 267 gold per 2-min steal) work for you. We can adjust during testing.
- **Start Coding**: I'll begin drafting the game server code in Python. We'll use a simple database like SQLite to store game state.
- **Get API Details**: You need to provide the endpoint and authentication for the CryptoGamer payout API so I can integrate it.
- **Test Relentlessly**: We'll test with small groups to balance the economy and fix bugs.

Your math is on point, and with human factors, the game should be tense and fun. Let's build this thing! What do you want to tackle first?

PROMPT 5: above is the structure of the cryptogamer miniapp as well as our whole miniapp logic on miniapp-overview.md with a folder made especially for games...miniapp.html is our main frontend face. we will need to create the Crypto Crew: Sabotage python game logic and all that is required as well as the Crypto Crew: Sabotage html version of the game. take a look and inform me on what files will be touched or tweaked and what files we need to create.

Based on the provided structure of the CryptoGamer miniapp and the requirements for integrating "Crypto Crew: Sabotage", here's a detailed plan on what files need to be created or modified. This will ensure the game is seamlessly integrated into the existing system while maintaining the overall miniapp style and functionality.

### Files to Create
1. **Backend Game Logic**:
   - `CryptoGamer/games/sabotage_game.py`: This file will contain the core game logic, including player role assignment, task management, stealing mechanics, voting, bribery, and win condition checks. It will handle real-time game state and interact with the database and Telegram bot.

2. **Frontend Game Interface**:
   - `CryptoGamer/static/sabotage/index.html`: The main HTML file for the game interface. It will include the spaceship map with clickable rooms, task mini-games, and UI elements for actions (e.g., call meeting, perform task). It should follow the miniapp style (black background, yellow buttons, glowing effects).
   - `CryptoGamer/static/sabotage/sabotage.css`: CSS file for styling the game interface, including animations for glowing balls, gradients, and room designs.
   - `CryptoGamer/static/sabotage/sabotage.js`: JavaScript file for client-side game logic, handling user interactions, communication with the backend via WebSockets or API calls, and rendering mini-games.

3. **Assets Directory**:
   - `CryptoGamer/static/sabotage/assets/`: Directory for game assets like images (spaceship rooms, character avatars), icons, and sound effects (if any).

### Files to Modify
1. **Miniapp Template**:
   - `CryptoGamer/templates/miniapp.html`: Add a new button or link for "Crypto Crew: Sabotage" in the GAMES section. This will allow users to access the game from the main miniapp interface.

2. **Database Models**:
   - `CryptoGamer/src/database/models.py`: Add new models for `SabotageGameSession`, `SabotagePlayer`, and `SabotageAction` to store game state, player roles, actions, and outcomes. This will support persistence and game history.
   - `CryptoGamer/src/database/schemas.py`: Add Pydantic schemas for the new models to handle data validation and serialization.

3. **API Routes**:
   - `CryptoGamer/src/web/routes.py`: Add new API endpoints for game actions, such as:
     - `POST /sabotage/start`: Start a new game session.
     - `POST /sabotage/action`: Perform an action (task, steal, bribe).
     - `POST /sabotage/meeting`: Call an emergency meeting and handle voting.
     - `POST /sabotage/end`: End the game and trigger payout.
   - These routes will interact with `sabotage_game.py` and the database.

4. **Telegram Integration**:
   - `CryptoGamer/src/telegram/commands.py`: Add a new command like `/sabotage` to allow users to start a game from the Telegram bot. This command could create a lobby and invite players.
   - `CryptoGamer/src/telegram/callbacks.py`: Handle callback queries for in-game actions, such as voting polls or bribery offers via direct messages.
   - `CryptoGamer/src/telegram/messages.py`: Add predefined messages for game notifications (e.g., role assignment, meeting calls, game results).

5. **Token Distribution**:
   - `CryptoGamer/src/features/mining/token_distribution.py`: Add a function `award_sabotage_gc(game_session_id)` to distribute the 8000 GC prize pool based on the game outcome. This function will be called after the game ends and will update player balances in the database.

6. **WebSocket Support**:
   - `CryptoGamer/static/js/websocket.js`: Extend the existing WebSocket functionality to handle real-time updates for the sabotage game, such as action confirmations, meeting calls, and vote results. Alternatively, create a new WebSocket handler in `sabotage.js` if needed.

7. **Quests and Missions**:
   - `CryptoGamer/src/features/quests.py`: Consider adding quests related to playing "Crypto Crew: Sabotage" (e.g., "Play 5 games of Sabotage" or "Win as a Saboteur"). This can drive engagement but is optional for initial release.

### Implementation Notes
- **Game Economy**: The backend logic in `sabotage_game.py` will calculate the in-game gold based on the balanced rates (Miners: 134 GC per task, Saboteurs: 267 GC per steal). The payout will be handled via `token_distribution.py`.
- **Real-Time Communication**: Use WebSockets for real-time updates to keep the game synchronized across all players. The existing `websocket.js` can be leveraged, or a separate WebSocket connection can be established for the game.
- **Style Consistency**: Ensure the game frontend follows the miniapp's design guidelines: black background, yellow buttons, glowing balls, and gradients. The CSS in `sabotage.css` should import or mimic styles from `main.css` and `miniapp.css`.
- **Testing**: Test the game thoroughly locally before deployment. Focus on game balance, network latency, and database interactions.

### Next Steps
1. Start by creating the backend game logic in `sabotage_game.py` and the database models.
2. Develop the frontend HTML, CSS, and JS files for the game interface.
3. Integrate the game into the miniapp by modifying the necessary files.
4. Test the game with a small group of users to refine mechanics and balance.

This approach ensures that "Crypto Crew: Sabotage" becomes a cohesive part of the CryptoGamer miniapp, leveraging existing systems for rewards and user management. Let me know if you need further details on any specific part!