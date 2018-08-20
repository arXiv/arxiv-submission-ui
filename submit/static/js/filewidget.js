/**
  * Populate the upload selection widget with a filename.
  **/
var update_filename = function() {
    if(file.files.length > 0) {
        document.getElementById('filename').innerHTML = file.files[0].name;
    }
};

/**
  * Bind the filename updater to the upload widget.
  **/
window.addEventListener('DOMContentLoaded', function() {
    var file = document.getElementById("file");
    file.onchange = update_filename;
});
