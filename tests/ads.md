AADS= <div id="frame" style="width: 100%;"><iframe data-aa='2405512' src='//acceptable.a-ads.com/2405512' style='border:0px; padding:0; width:100%; height:100%; overflow:hidden; background-color: transparent;'></iframe><a style="display: block; text-align: right; font-size: 12px" id="frame-link" href="https://aads.com/campaigns/new/?source_id=2405512&source_type=ad_unit&partner=2405512">Advertise here</a></div>

monetag - place tag below the <head> tag of your app's source code. --> tag --> <script src='//libtl.com/sdk.js' data-zone='9644715' data-sdk='show_9644715'></script>



// Rewarded interstitial

        show_9644715().then(() => {
            // You need to add your user reward function here, which will be executed after the user watches the ad.
            // For more details, please refer to the detailed instructions.
            alert('You have seen an ad!');
        })

                
        //Rewarded Popup


        // Rewarded Popup

        show_9644715('pop').then(() => {
            // user watch ad till the end or close it in interstitial format
            // your code to reward user for rewarded format
        }).catch(e => {
            // user get error during playing ad
            // do nothing or whatever you want
        })




// In-App Interstitial

        show_9644715({
        type: 'inApp',
        inAppSettings: {
            frequency: 2,
            capping: 0.1,
            interval: 30,
            timeout: 5,
            everyPage: false
        }
        })

        /*
        This value is decoded as follows:
        - show automatically 2 ads
        within 0.1 hours (6 minutes)
        with a 30-second interval between them
        and a 5-second delay before the first one is shown.
        The last digit, 0, means that the session will be saved when you navigate between pages.
        If you set the last digit as 1, then at any transition between pages,
        the session will be reset, and the ads will start again.
        */



// CoinZilla = <meta name="coinzilla" content="9fda59ba338e70de68b544ca329dc8a8" />
