from Tkinter import *
import ssm
import threading
import time

debug = False
#debug = True

class AppUI(Frame):
    def __init__(self, params, param_lists):
        Frame.__init__(self)
        self.master.title('SSM 1.5 Scanner')
        self.pack()

        # Set the read_thread to none until it gets assigned.
        self.read_thread = None

        # Start with no logging.
        self.log = False

        # Set log file
        self.logfile = None

        # Create the frame for the buttons.
        self.buttons_frame = Frame(self)
        self.buttons_frame.pack()

        # Create the "Log" button.
        log_button = Button(self.buttons_frame, text='Log')
        log_button.config(command=self.toggle_log)
        log_button.grid(row=0, column=0, sticky=W+E, padx=5, pady=5)

        # Create the "All" button.
        all_button = Button(self.buttons_frame, text='All')
        all_button.config(command=lambda text='All': self.switch_param_list('All'))
        all_button.grid(row=0, column=1, sticky=W+E, padx=5, pady=5)

        # Create the "All" frame.
        all_frame = Frame(self)

        # Add it to the frame_list for the ui.  All frames have names corresponding to their buttons.
        self.frame_list = {'All': all_frame}

        # Set the font to be used with this ui.
        ui_font = ('Verdana', 10)

        # Calculate width of the description labels.
        desc_len = 0
        for param in params:
            if len(param.desc) > desc_len:
                desc_len = len(param.desc)
        #
        # Assemble the "All" frame.
        i = 0
        for param in params:
            Label(all_frame, text=param.desc, font=ui_font, anchor=W, justify=LEFT, width=desc_len).grid(row=i, column=0, sticky=W+E, padx=5, pady=5)
            param.set_textvar(StringVar())
            Label(all_frame, text='---', textvar=param.textvar, font=ui_font, anchor=E, justify=RIGHT, width=8).grid(row=i, column=1, sticky=W+E, padx=5, pady=5)
            Label(all_frame, text=param.units, font=ui_font, anchor=W, justify=LEFT).grid(row=i, column=2, sticky=W+E, padx=5, pady=5)
            i += 1

        # Assemble the rest of the frames.
        i = 2
        for list_ in sorted(param_lists):
            # Create the button for each set of parameters.
            a_button = Button(self.buttons_frame, text=list_)
            a_button.config(command=lambda text=a_button['text']: self.switch_param_list(text))
            a_button.grid(row=0, column=i, sticky=W+E, padx=5, pady=5)

            # Create the frame for each set of parameters.
            a_frame = Frame(self)
            self.frame_list[list_] = a_frame

            # Populate this frame's parameters.
            j = 0
            for param_ in param_lists[list_]:
                Label(a_frame, text=param_.desc, font=ui_font, anchor=W, justify=LEFT, width=desc_len).grid(row=j, column=0, sticky=W+E, padx=5, pady=5)
                Label(a_frame, textvar=param_.textvar, font=ui_font, anchor=E, justify=RIGHT, width=8).grid(row=j, column=1, sticky=W+E, padx=5, pady=5)
                Label(a_frame, text=param_.units, font=ui_font, anchor=W, justify=LEFT).grid(row=j, column=2, sticky=W+E, padx=5, pady=5)
                j += 1
            i += 1

        # Set the list of lists(?) for the ui.
        self.param_lists = {'All': params}
        self.param_lists.update(param_lists)

        # Set the current list's name.
        self.current_list = 'All'

        # Set the ui's active params as the "All" list.
        self.switch_param_list('All')

    def switch_param_list(self, list_):
        # Debug message to be removed later.
#        print 'INFO: Switching to {0} parameters.'.format(list_)

        # Hide the old frame.
        self.frame_list[self.current_list].forget()

        # Update the current_list variable.
        self.current_list = list_

        # Show the new frame.
        self.frame_list[self.current_list].pack()

        # Switch the active parameters to the new list.
        self.active_params = self.param_lists[self.current_list]

        if self.log:
            self.stop_log()
            self.start_log()

        if self.read_thread is not None:
            self.read_thread.new_params = True

#        active_list = self.active_params
#        print 'INFO: Lowest address: {0:04x} Highest addres: {1:04x}.'.format(active_list.get_lowest_address(), active_list.get_highest_address())

    def assign_read_thread(self, thread):
        self.read_thread = thread

    def start_log(self):
        self.logfile = open('./logs/submon-'+time.strftime("%Y_%m_%d_%H_%M_%S")+'.csv', 'w')
        self.logfile.write('Time,')
        for param in self.active_params:
            self.logfile.write('{0.desc},'.format(param))
        self.logfile.write('\n')
        self.log = True
        print 'Log started!'
        self.basetime = time.time()

    def stop_log(self):
        self.logfile.close()
        self.log = False
        print 'Log stopped!'

    def toggle_log(self):
        if self.log:
            self.stop_log()
        else:
            self.start_log()

    def update_refresh_rate(self):
        frequency = 0
        if self.delta != 0:
           frequency = 1.0 / self.delta
        self.master.title('SSM 1.5 Scanner at {0:0.2f} Hz (every {1:0.0f} ms)'.format(frequency, 1000 * self.delta))

    def set_update_period(self, new_delta):
        self.delta = new_delta
        self.after_idle(self.update_refresh_rate)

class ReadThread(threading.Thread):
    def __init__(self, s, ui):
        threading.Thread.__init__(self)
        self.s = s
        self.ui = ui
        self.setDaemon(True)
        self.new_params = False
        self.update_params()

    def update_params(self):
        self.params = self.ui.active_params
        self.low_address = self.params.get_lowest_address()
        self.adh = self.low_address / 256
        self.adhc = chr(self.adh)
        self.adl = self.low_address % 256
        self.adlc = chr(self.adl)
        self.length = self.ui.active_params.get_highest_address() - self.low_address + 1
#        for param in self.params:
#            print 'Param: {0}'.format(param.desc)

    def run(self):
        self.s.ask_ecu(self.adhc, self.adlc, self.length)
        t1_time = time.time()
        while True:
            ecu_data = self.s.read_ecu_data(self.adhc, self.adlc, self.length)
            if self.new_params:
                self.update_params()
                self.new_params = False
                ecu_data = None
            if ecu_data is None:
                self.s.flush()
                self.s.ask_ecu(self.adhc, self.adlc, self.length)
                continue
#            print 'ecu_data: {0}'.format(tuple(ecu_data))
            if self.ui.log:
                self.ui.logfile.write('{0},'.format(time.time() - self.ui.basetime))
            for param in self.params:
                if param.address == '$ValueError':
                    continue
                elif param.address == None:
                    param.set_value(0)
                    if self.ui.log:
                        self.ui.logfile.write('{0},'.format(param.get_fvalue()))
                else:
#                    print 'Debug: param: {2}, ecu_data ({1}): {0}'.format(tuple(ecu_data), len(ecu_data), param.desc)
#                    print 'Debug: address: {0}'.format(param.address)
#                    print 'Debug: low_address: {0}'.format(self.low_address)
                    param.set_value(ord(ecu_data[param.address - self.low_address]))
                    if self.ui.log:
                        self.ui.logfile.write('{0},'.format(param.get_fvalue()))
            if self.ui.log:
                self.ui.logfile.write('\n')
            t2_time = time.time()
            delta_t = t2_time - t1_time
            self.ui.set_update_period(delta_t)
#            self.ui.update_refresh_rate(1.0 / delta_t)
            t1_time = t2_time

param_file = open('params.csv', 'r')
params = ssm.load_param_file(param_file)
param_file.close()

list_file = open('param_lists.txt', 'r')
param_lists = ssm.load_list_file(list_file, params)
list_file.close()

##log_file = open('./logs/submon-'+time.strftime("%Y_%m_%d_%H_%M_%S")+'.csv', 'w')

if not debug:
    try:
        with open("port.txt", "r") as f:
            port_name = f.readline()[:-1]
##            print 'port="{0}"'.format(port_name)
            s = ssm.Port(device=port_name)
    except:
        print 'Unable to open the SSM Port!  Exiting...'
        print ''
        input('Press any key to quit...')
        exit(-1)

    ui = AppUI(params, param_lists)
    read_thread = ReadThread(s, ui)
    ui.assign_read_thread(read_thread)
    read_thread.start()
    
ui.mainloop()
ui.logfile.close()
##log_file.close()
