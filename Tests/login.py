import customtkinter as ctk
import tkinter.messagebox as tkmb


# Selecting GUI theme - dark, light , system (for system default)
ctk.set_appearance_mode("dark")

# Selecting color theme - blue, green, dark-blue
ctk.set_default_color_theme("blue")





class InputFrame(ctk.CTkFrame):
    def __init__(self,master):
        super().__init__(master)

        self.pack(pady=20,padx=40,fill='both',expand=True)  
        self.label = ctk.CTkLabel(master=self,text='Modern Login System UI')
        self.label.pack(pady=12,padx=10)      

        self.user_entry= ctk.CTkEntry(master=self,placeholder_text="Username")
        self.user_entry.pack(pady=12,padx=10)

        self.user_pass= ctk.CTkEntry(master=self,placeholder_text="Password",show="*")
        self.user_pass.pack(pady=12,padx=10)

        self.button = ctk.CTkButton(master=self,text='Login',command=self.login())
        self.button.pack(pady=12,padx=10)

        self.checkbox = ctk.CTkCheckBox(master=self,text='Remember Me')
        self.checkbox.pack(pady=12,padx=10)

    def login(self):
        username = "Geeks"
        password = "12345"


        print('button is pressed')
        if self.user_entry.get() == username and self.user_pass.get() == password:
                tkmb.showinfo(title="Login Successful",message="You have logged in Successfully")
        
        
        


class Login(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("400x400")
        self.title("Modern Login UI using Customtkinter")

        self.label = ctk.CTkLabel(self,text="This is the main UI page")
        self.label.pack(pady=20)

        self.input_frame = InputFrame(self)


if __name__ == "__main__":
    login = Login()
    login.mainloop()