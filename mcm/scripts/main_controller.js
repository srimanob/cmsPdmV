function mainCtrl($scope, $http, $location, $window){
  $scope.user = {name: "guest", role:"user",roleIndex:0};

// GET username and role
    var promise = $http.get("restapi/users/get_roles");
    promise.then(function(data){
      $scope.user.name = data.data.username;
      $scope.user.role = data.data.roles[0];
      $scope.user.roleIndex = parseInt(data.data.role_index);
    },function(data){
      alert("Error getting user information. Error: "+data.status);
    });
// Endo of user info request

  $scope.isDevMachine = function(){
    return $location.absUrl().indexOf("dev") != -1;
  };
  //return everyting thats after main url
  $scope.getLocation = function(){
    return $location.url();
  };

  $scope.role = function(priority){
    if(priority > $scope.user.roleIndex){ //if user.priority < button priority then hide=true
      return true;
    }else{
      return false;
    }
  };
  //watch length of pending HTTP requests -> if there are display loading;
  $scope.$watch(function(){ return $http.pendingRequests.length;}, function(v){
    if (v == 0){  //if HTTP requests pending == 0
      $scope.pendingHTTP = false;
    }else
      $scope.pendingHTTP = true;
  });

};