#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2015, Steinar Bang ; 2020, un_pogaz <un.pogaz@gmail.com>'
__docformat__ = 'restructuredtext en'

try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from calibre.customize import InterfaceActionBase

class ActionOpdsReader(InterfaceActionBase):
    '''
    An OPDS client that can read the OPDS of a different calibre,
    and display the differences between this calibre and the other
    and download the missing books from the other calibre
    '''
    name = 'OPDS Reader'
    description = _('Import the books from a OPDS catalog')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Steinar Bang & un_pogaz'
    version = (2, 0, 0)
    minimum_calibre_version = (2, 0, 0)
    
    actual_plugin = __name__+'.action:OpdsReaderAction'
    
    DEBUG_PRE = 'OPDSreader'
    
    def is_customizable(self):
        return True
    
    def config_widget(self):
        from calibre_plugins.opds_client.config import ConfigWidget
        return ConfigWidget()
    
    def save_settings(self, config_widget):
        config_widget.save_settings()
        
        ac = self.actual_plugin_
        if ac is not None:
            ac.apply_settings()
