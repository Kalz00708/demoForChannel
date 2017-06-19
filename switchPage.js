/**
 * Created by lz on 2017/3/22.
 */

$("#trades").click(function () {
    $(this).addClass("active");
    $(this).next().removeClass("active");
    $("#trade-list").show();
    $("#blotter-list").hide();
});

$("#blotter").click(function () {
    $(this).addClass("active");
    $(this).prev().removeClass("active");
    $("#trade-list").removeClass("active").hide();
    $("#blotter-list").addClass("active").show();
});