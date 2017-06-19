/**
 * Created by lz on 2017/2/14.
 */
var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
var ws_path = ws_scheme + '://' + window.location.host;
var socket = new WebSocket(ws_path);
var headOfOverview = $('#gentext tr:first');

// the template of the expending of the trade list
function getPending(trade) {
    return $('<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px; color:white">' +
        '<tr style="color:white">' +
        '<td>Contra Amount:</td>'+
        '<td>'+trade.contra_amount+'</td>'+
        '</tr>'+
        '<tr style="color:white">'+
        '<td >Telephone Number:</td>'+
        '<td>'+trade.seller_phone+'</td>'+
        '</tr>'+
        '<tr style="color:white">'+
        '<td><button value="'+ trade.id +'" class="accept">AFFIRM TRADE</button></td>'+
        '<td><button value="'+ trade.id +'" class="reject">REJECT TRADE</button></td>'+
        '<td><button value="'+ trade.seller_phone +'" class="call"">CALL CLIENT</button></td>'+
        '</tr>'+
        '</table>');
}

// the template of the expending of trade history
function getHistory(trade) {
    return $('<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">' +
        '<tr>' +
        '<td>Contra Amount:</td>' +
        '<td>'+trade.contra_amount+'</td>' +
        '</tr>' +
        '<tr>' +
        '<td>Last actioned by:</td>' +
        '<td>'+trade.modified_by_name+'</td>' +
        '</tr>' +
        '<tr>' +
        '<td>Reason if rejected:</td>' +
        '<td>'+trade.reason+'</td>' +
        '</tr>' +
        '<tr>' +
        '<td><button value="'+ trade.id +'" class="call">REVERT TRADE</button></td>' +
        '</tr>' +
        '</table>');
}

function insertIntoTradelist(trade) {
    var date = new Date(trade.time_pushed);

    // get the expending of the trade list table of that row
    var pending = getPending(trade);

    // generate a trade list table row
    var tradeData = [trade.id,
        date.toLocaleString("en-US"),
        trade.buyer_name,
        '$' + trade.amount_millions + 'm',
        trade.currency_pair,
        trade.rate,
        trade.seller_name,
        trade.trade_type];
    tradeData.id = trade.id;
    table.row.add(tradeData).draw().child(pending);

    // add the accept method to the new row
    pending.find(".accept").click(function() {
        var x;
        if (confirm("Are you sure you wish to AFFIRM trade ID " + $(this).val()) == true) {
            x = "You pressed OK!";
            socket.send(JSON.stringify({
                "command": "affirm",
                "id":$(this).val()
            }));
        } else {
            x = "You pressed Cancel!";
        }
    });

    // add the reject method to the new row
    pending.find(".reject").click(function() {
        var reason = prompt("Reason required for rejecting trade " + $(this).val(), "");

        while (reason == ""){
            var reason = prompt("ERROR: Reason not provided. \nReason required for rejecting trade " + $(this).val(), "");
        }

        if(reason != null){
            socket.send(JSON.stringify({
                "command": "reject",
                "reason": reason,
                "id":$(this).val()
            }));
        }
    });

    // add the call method to the new row
    pending.find(".call").click(function() {
        var x;
        if (confirm("Calling client on " + $(this).val()) == true) {
            x = "You pressed OK!";
        } else {
            x = "You pressed Cancel!";
        }
    });
}


// insert the pending trade into the blotter and its overview
function insertIntoHistory(trade) {
    var push = new Date(trade.time_pushed);
    var action = new Date(trade.time_actioned);

    // get the expending of the blotter table of that row
    var history = getHistory(trade);

    // generate a blotter table row
    var tradeData = [trade.id,
        push.toLocaleString("en-US"),
        trade.buyer_name,
        '$' + trade.amount_millions + 'm',
        trade.rate,
        trade.currency_pair,
        trade.seller_name,
        trade.trade_type,
        trade.status,
        action.toLocaleString("en-US")];
    tradeData.id = trade.id;

    // insert into the blotter
    table2.row.add(tradeData).draw().child(history);

    // add the call method to the new row
    history.find(".call").click(function() {
        var reason = prompt("Reason required for reverting trade " + $(this).val(), "");
        while (reason == ""){
            var reason = prompt("ERROR: Reason not provided. \nReason required for reverting trade " + $(this).val(), "");
        }

        if(reason != null){
            socket.send(JSON.stringify({
                "command": "revert",
                "reason": reason,
                "id":$(this).val()
            }));
        }
    });

    // insert into the blotter overview
    headOfOverview.after('<tr id="overview_' + trade.id + '">' +
        '<td>' + trade.id +'</td>' +
        '<td>' + action.toLocaleString("en-US") + '</td>' +
        '<td>' + trade.status + '</td>' +
        '</tr>');
}

// Handle incoming messages from server
socket.onmessage = function (message) {
    var response = JSON.parse(message.data);  // the response mesage
    var html;

    // insert the pending trade into trade list
    for(var t in response.add_p) {
        var trade = response.add_p[t];
        insertIntoTradelist(trade);
    }

    // insert the history trade into the blotter
    for(var t in response.add_h){
        var trade = response.add_h[t];
        insertIntoHistory(trade);
    }


    if(response.del.has_del){
        if(response.del.action) {
            // remove the reverted trade from blotter
            table2.row("#history_" + response.del.trade.id).remove().draw();
            // remove the reverted trade from blotter overview
            $("#overview_" + response.del.trade.id).remove();
            // insert the reverted trade into the trade list
            insertIntoTradelist(response.del.trade);
        } else {
            // remove the pending trade from trade list
            table.row("#pending_" + response.del.trade.id).remove().draw();
            // insert the pending trade into the blotter and its overview
            insertIntoHistory(response.del.trade);
        }
    }
};

socket.onopen = function () {
    console.log("Connected to chat socket");
};
socket.onclose = function () {
    console.log("Disconnected from chat socket");
}