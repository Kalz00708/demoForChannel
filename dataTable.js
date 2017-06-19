// table of trade list
var table = $('#example').DataTable({
    "createdRow" : function( row, data, index ) {
        if( data.hasOwnProperty("id") ) {
            row.id = "pending_" + data.id;
        }
    }
});

$('#example tbody').on( 'click', 'tr', function () {
    var child = table.row( this ).child;

    if ( child.isShown() ) {
        child.hide();
    }
    else {
        child.show();
    }
} );


// table of trade history
var table2 = $('#example2').DataTable({
    "createdRow" : function( row, data, index ) {
        if( data.hasOwnProperty("id") ) {
            row.id = "history_" + data.id;
        }
    }
});

table2.rows().every( function () {
    this.child( 'Row details for row: '+this.index() );
} );

$('#example2 tbody').on( 'click', 'tr', function () {
    var child = table2.row( this ).child;

    if ( child.isShown() ) {
        child.hide();
    }
    else {
        child.show();
    }
} );