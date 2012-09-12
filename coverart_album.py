# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2012 - fossfreedom
# Copyright (C) 2012 - Agustin Carrasco
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

from gi.repository import RB
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import GdkPixbuf

import os
import cgi
import rb

class AlbumLoader( object ):
    DEFAULT_LOAD_CHUNK = 10

    def __init__( self, plugin ):
        self.albums = {}
        self.cover_db = RB.ExtDB( name='album-art' )

        self.req_id = self.cover_db.connect( 'added',
                                             self.albumart_added_callback )

        Album.init_unknown_cover( plugin )
    
    def albumart_added_callback( self, ext_db, obj, p0, p1 ):
        # called when new album art added
        # parameters: ext_db - this is the album-art database
        # obj = RB.ExtDBKey
        # p0 = full path to cached album art file
        # p1 = pixbuf of the album art file
        print "CoverArtBrowser DEBUG - albumart_added_callback"
        
        album_name = obj.get_field("album")
        print album_name

        # use the name to get the album and update the cover
        self.albums[album_name].update_cover( p1 )

        print "CoverArtBrowser DEBUG - end albumart_added_callback"
       
    def load_albums( self, db, cover_model ):
        #build the query
        q = GLib.PtrArray()
        db.query_append_params( q,
              RB.RhythmDBQueryType.EQUALS, 
              RB.RhythmDBPropType.TYPE, 
              db.entry_type_get_by_name( 'song' ) )
              
        #create the model and connect to the completed signal
        qm = RB.RhythmDBQueryModel.new_empty( db )
        
        qm.connect( 'complete', self._query_complete_callback, cover_model )
        
        db.do_full_query_async_parsed( qm, q )
        
    def _query_complete_callback( self, qm, cover_model ):     
        qm.foreach( self._process_entry, None )
    
        self._fill_model( cover_model )
        
    def _process_entry( self, model, tree_path, tree_iter, _ ):
        (entry,) = model.get( tree_iter, 0 )
    
        album_name = entry.get_string( RB.RhythmDBPropType.ALBUM )
        artist = entry.get_string( RB.RhythmDBPropType.ARTIST ) 
               
        if album_name in self.albums.keys():
            album = self.albums[album_name]
        else:
            album = Album( album_name, artist )
            self.albums[album_name] = album
            
        album.append_entry( entry )
        
    def _fill_model( self, model ):
        Gdk.threads_add_idle( GLib.PRIORITY_DEFAULT_IDLE, 
                              self._idle_load_callback, 
                              (model, self.albums.values()) )

    def _idle_load_callback( self, data ):
        model, albums = data
     
        for i in range( AlbumLoader.DEFAULT_LOAD_CHUNK ):
            try:
                album = albums.pop()
                album.load_cover( self.cover_db  )
                album.add_to_model( model )
            except:
                return False
        
        return True

class Album( object ):
    UNKNOWN_COVER = 'rhythmbox-missing-artwork.svg'

    def __init__( self, name, artist ):
        # name is the album name
        # artist is the artist name
        
        self.name = name
        self.artist = artist
        self.entries = []
        self.cover = Album.UNKNOWN_COVER
        
    def append_entry( self, entry ):
        self.entries.append( entry )
        
    def load_cover( self, cover_db ):
        key = self.entries[0].create_ext_db_key( RB.RhythmDBPropType.ALBUM )
        art_location = cover_db.lookup( key )
        
        if art_location and os.path.exists( art_location ):
            try:
                self.cover = Cover( art_location )
            except:
                self.cover = Album.UNKNOWN_COVER
        
    def add_to_model( self, model ):   
        self.model = model
        self.tree_iter = model.append( 
            (cgi.escape( '%s - %s' % (self.artist, self.name) ),
            self.cover.pixbuf, 
            self) )

    def update_cover( self, pixbuf ):
        self.cover.change_pixbuf( pixbuf )
        self.model.set_value( self.tree_iter, 1, self.cover.pixbuf )

    def get_track_count( self ):
        return len( self.entries )
        
    def calculate_duration_in_secs( self ):
        duration = 0
        
        for entry in self.entries:
            duration += entry.get_ulong( RB.RhythmDBPropType.DURATION )
        
        return duration
    
    def calculate_duration_in_mins( self ):
        return self.calculate_duration_in_secs() / 60        
                    
    @classmethod
    def init_unknown_cover( cls, plugin ):
        if type( cls.UNKNOWN_COVER ) is str:
            cls.UNKNOWN_COVER = Cover( rb.find_plugin_file( plugin, 
                                                           cls.UNKNOWN_COVER ) )                         
        
class Cover( object ):
    COVER_SIZE = 92
    
    def __init__( self, file_path, width=COVER_SIZE, height=COVER_SIZE ):
        self.width = width
        self.height = height
    
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size( file_path, 
                                                              self.width, 
                                                              self.height )
                                                              
    def change_pixbuf( self, pixbuf ):
        self.pixbuf = pixbuf.scale_simple( self.width, 
                                           self.height,
                                           GdkPixbuf.InterpType.BILINEAR )
