miniapp.css
CSS 12.61KB
miniapp_overview.txt
TXT 4.28KB
CryptoGamer.md
MD 6.2KB
we have  a few issues after testing the production deployment of our CyptoGamer project and a few implementations we want to add:
 
--> the games when clicked open a page that shows 'page not found'
--> our rewards are supposed to be in game-coins(gc) which can later be converted to ton
--> our "connect wallet" button fails. it is supposed to open the telegram wallet of the user urging them to connect their wallet so that things like in-game purchases are possible form the shop.
--> let the game cards' length/horizontal length be shorter so that 2 games are comfortably fitted in one row in order to maximize space for ads. also do this in the games page.
--> the adbanner slot is quite short vertically...adjust it in a way that we can be able to place atleast about 2 ads on the home page
--> switch the withdraw to request withdrawal
--> Display balance in terms of gc coins instead of ton...show the equivical of gc to ton in theprofile and wallet section.
--> add back button to make it easier to navigate the app
--> let the shop hover over every part of the app
--> add names to the button pages to avoid confusion
--> also add a function in otc exchange so that when a user inputs their amount and clicks on swap function, it asks them to enter the phone number they will recieve their fiat in if the currency == kes...if currency == usd/eur, enter paypal email/details to recieve the usd..if currency == usdt, enter wallet address.
--> add colour to the other buttons that indicates they are clickable in QUESTS page...you can use different colours for each button per the page it directs the user to.
--> let all new users balance start at 0 with a popup for entering the game with a reward of 2000 gc and a daily bonus of 1000gc per day.
--> withdrawals can only be made if the user has a 75% participation in all parts and quests in the app including referrals.
--> add 3 more slots in the WATCH page for ads to be watched.
--> implement the ads in ads.md
--> fix the urls in the app especially the game urls keepin in mind that we are running the whole app from render server...follow the CryptoGamer structure and write the links to paths in full if that is what is requied.