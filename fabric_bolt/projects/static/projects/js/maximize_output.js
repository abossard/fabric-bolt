$(function(){
  var well = $('#deployment_well');
  var well_parent = well.parent();
  var original_pos = $('#deployment_well').position();
  var deployment_text = $('#deployment_text');
  var original_text_height = deployment_text.css('height');

  $("#deployment_maximize").click(function(){
    var minimize = $(this).clone().attr('id', 'deployment_minimize');
    minimize.text('Minimize')
    minimize.click(function(){
      $(this).hide();
      $("#deployment_maximize").show();

      well_parent.append(well)
      well.css({width: '100%', height : '100%', top: 0, left: 0}).animate({
        'position' : 'absolute', left: original_pos.left + 'px', top: original_pos.top + 'px'
      },100);
      $("body").css({ overflow: 'inherit' })
      deployment_text.css(original_text_height)
    });

    // Scroll to the top so the overflow hack works nicely
    window.scrollTo(0, 0)
    $(this).hide();
    $('body').append(well)
    well.prepend(minimize);

    well.css({'position' : 'absolute', left: original_pos.left + 'px', top: original_pos.top + 'px'}).animate({
      width: '100%', height : '100%', top: 0, left: 0
    },100);
    $("body").css({ overflow: 'hidden' })
    deployment_text.css({height: '100%'})
  });
});
