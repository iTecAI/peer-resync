var PREV = {};

function condition(c, t, f) { if (c) { return t; } else { return f; } }

function refresh_update(result) {
    var peers = {};
    for (var k = 0; k < Object.keys(result.peers.local).length; k++) {
        var key = Object.keys(result.peers.local)[k];
        var peer = result.peers.local[Object.keys(result.peers.local)[k]];
        peers[key] = {
            'local': peer,
            'remote': null
        };
    }
    for (var k = 0; k < Object.keys(result.peers.remote).length; k++) {
        var key = Object.keys(result.peers.remote)[k];
        var peer = result.peers.remote[Object.keys(result.peers.remote)[k]];
        if (!Object.keys(peers).includes(key)) {
            peers[key] = {
                'local': null,
                'remote': peer
            }
        } else {
            peers[key].remote = peer;
        }
    }
    console.log(peers);

    var pkeys = Object.keys(peers);
    var dummy_peers = $('<div id="peers" class="noscroll"></div>');
    for (var p = 0; p < pkeys.length; p++) {
        var peer = peers[pkeys[p]];
        var one_peer = $('<div class="peer"></div>');
        one_peer.attr('id', pkeys[p]);
        one_peer.append($('<span class="peer-name noselect"></span>').text(pkeys[p]));
        one_peer.append($('<span class="peer-local peer-connection"></span>').append($('<span class="material-icons noselect">home</span>')).append(condition(peer.local == null, '[no local connection]', peer.local.join(':'))));
        one_peer.append($('<span class="peer-remote peer-connection"></span>').append($('<span class="material-icons noselect">podcasts</span>')).append(condition(peer.remote == null, '[no remote connection]', peer.remote.join(', '))));

        one_peer.appendTo(dummy_peers);
    }
    dummy_peers.replaceAll('#peers');

    console.log(result.folders);
    var dummy_folders = $('<div id="folders" class="noscroll"></div>');
    for (var f = 0; f < Object.keys(result.folders).length; f++) {
        var folder = result.folders[Object.keys(result.folders)[f]];
        var folder_el = $('<div class="folder-item"></div>')
        folder_el.attr('data-path', folder.display_path);
        folder_el.append($('<div class="folder-title"></div>').text(folder.display_path));
        folder_el.append(
            $('<button class="push-updates top-button noselect"></button>')
                .append('<span class="material-icons">arrow_upward</span> <span>Push Updates</span>')
        );
        folder_el.append(
            $('<button class="delete-folder top-button noselect"></button>')
                .append('<span class="material-icons">delete</span> <span>Stop Tracking</span>')
                .on('click', function (event) {
                    $.post({
                        url: '../folders/stop_tracking',
                        data: JSON.stringify({
                            folder_path: $(this).parents('.folder-item').attr('data-path')
                        })
                    }).fail(function (data) {
                        if (data.status == 404) {
                            alert('Invalid path. Error message: ' + data.result);
                        } else {
                            console.log(data);
                            alert('An unexpected error occurred. Check server logs.');
                        }
                    });
                })
        );
        folder_el.append(
            $('<span class="folder-buffer noselect"></span>')
                .append('<span class="material-icons">edit</span>')
                .append(folder.commands.mods.toString())
                .append('<span class="material-icons">delete</span>')
                .append(folder.commands.dels.toString())
        );
        folder_el.append(
            $('<div class="excluded-folders"></div>')
                .append(folder.excluded_paths.map(function (v) {
                    return $('<span class="excluded-folder-item"></div>')
                        .append(
                            $('<button class="noselect">[=]</button>')
                        )
                        .append(
                            $('<span class="noselect">Excluded Folders</span>')
                        );
                }))
                .append(folder.excluded_paths.map(function (v) {
                    return $('<span class="excluded-folder-item"></div>')
                        .attr('data-path', v)
                        .append(
                            $('<button class="noselect">[-]</button>')
                                .on('click', function (event) {
                                    $.post({
                                        url: '../folders/excluded/remove',
                                        data: JSON.stringify({
                                            folder_path: $(this).parents('.excluded-folder-item').parents('.excluded-folders').parents('.folder-item').attr('data-path'),
                                            excluded: $(this).parents('.excluded-folder-item').attr('data-path')
                                        })
                                    }).fail(function (data) {
                                        if (data.status == 404) {
                                            alert('Invalid path. Error message: ' + data.result);
                                        } else {
                                            console.log(data);
                                            alert('An unexpected error occurred. Check server logs.');
                                        }
                                    });
                                })
                        )
                        .append(
                            $('<span></span>').text($(folder_el).attr('data-path') + '/' + v)
                        );
                }))
                .append(
                    $('<span class="excluded-folder-item new-item"></div>')
                        .append(
                            $('<button class="noselect">[+]</button>')
                                .on('click', function (event) {
                                    if ($(this).parents('.excluded-folder-item').children('input').val().length == 0) {
                                        return;
                                    }
                                    $.post({
                                        url: '../folders/excluded/add',
                                        data: JSON.stringify({
                                            folder_path: $(this).parents('.excluded-folder-item').parents('.excluded-folders').parents('.folder-item').attr('data-path'),
                                            excluded: $(this).parents('.excluded-folder-item').children('input').val()
                                        })
                                    }).fail(function (data) {
                                        if (data.status == 404) {
                                            alert('Invalid path. Error message: ' + data.result);
                                        } else {
                                            console.log(data);
                                            alert('An unexpected error occurred. Check server logs.');
                                        }
                                    });
                                    $(this).parents('.excluded-folder-item').children('input').val('');
                                })
                        )
                        .append(
                            $('<input placeholder="Folder Path">')
                        )
                )
        );

        folder_el.appendTo(dummy_folders);
    }
    dummy_folders.replaceAll('#folders');
}

$(document).ready(function () {
    $.get('../', function (result) {
        $('#title-node-name').text(result.node_name);
        $('#network-name').text(result.network);
    });
    window.setInterval(function () {
        $.get('../refresh', function (result) {
            if (!_.isEqual(PREV, result)) {
                PREV = result;
                refresh_update(result);
            }
        });
    }, 250);
    $('#add-folder').on('click', function () {
        var fp = prompt('Enter path to folder.');
        if (Object.values(PREV.folders).some(function (v) { return v.system_path == fp; })) {
            alert('That folder is already being used.');
            return;
        }
        $.post({
            url: '../folders/new',
            data: JSON.stringify({ folder_path: fp })
        }).fail(function (data) {
            if (data.status == 404) {
                alert('Invalid path.');
            } else {
                console.log(data);
                alert('An unexpected error occurred. Check server logs.');
            }
        });
    });
});