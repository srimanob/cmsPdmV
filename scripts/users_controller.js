function resultsCtrl($scope, $http, $location, $window){
    $scope.defaults = [
        {text:'UserName', select:true, db_name:'username'},
        {text:'Actions', select:false, db_name:''},
        {text:'Email', select:false, db_name:'email'},
        {text:'Roles', select:true, db_name:'roles'}
    ];
    $scope.user = {name: "", role:""}
    $scope.update = [];
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
    $scope.show_well = false;

    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "users";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    if($location.search()["page"] === undefined){
      page = 0;
      $location.search("page", 0);
      $scope.list_page = 0;
    }else{
      page = $location.search()["page"];
      $scope.list_page = parseInt(page);
    }
    $scope.select_all_well = function(){
      $scope.selectedCount = true;
      var selectedCount = 0
      _.each($scope.defaults, function(elem){
        if (elem.select){
          selectedCount +=1;
        }
        elem.select = true;
      });
      if (selectedCount == _.size($scope.defaults)){
      _.each($scope.defaults, function(elem){
        elem.select = false;
      });
      $scope.defaults[0].select = true; //set prepid to be enabled by default
      $scope.defaults[3].select = true; // set actions to be enabled
      $scope.selectedCount = false;
      }
    };

    $scope.sort = {
      column: 'value.username',
      descending: false
    };

    $scope.selectedCls = function(column) {
        return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
    };
    
    $scope.changeSorting = function(column) {
      var sort = $scope.sort;
      if (sort.column == column) {
        sort.descending = !sort.descending;
      }else{
        sort.column = column;
        sort.descending = false;
      }
    };
  $scope.showing_well = function(){
        if ($scope.show_well){
          $scope.show_well = false;
        }
        else{
            console.log("true");
            $scope.show_well = true;
        }
    };
    
   $scope.$watch('list_page', function(){
      console.log("modified");
      var promise = $http.get("restapi/"+$scope.dbName+"/get_all_users")
       promise.then(function(data){
        console.log(data);
        $scope.result = data.data.results; 
        if ($scope.result.length != 0){
        columns = _.keys($scope.result[0]["value"]);
        rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
//         $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
        _.each(rejected, function(v){
            add = true;
            _.each($scope.defaults, function(column){
            if (column.db_name == v){
                add = false;
            }
         });
            if (add){
                $scope.defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
            }
        });
        }
        // console.log($scope.requests_defaults);
    }, function(){
       console.log("Error"); 
      });
    });

  $scope.previous_page = function(current_page){
      if (current_page >-1){
        $location.search("page", current_page-1);
        $scope.list_page = current_page-1;
      }
  };
  $scope.next_page = function(current_page){
      if ($scope.result.length !=0){
        $location.search("page", current_page+1);
        $scope.list_page = current_page+1;
      }
  };
  $scope.role = function(priority){
    if(priority > $scope.user.roleIndex){ //if user.priority < button priority then hide=true
      return true;
    }else{
      return false;
    }
  };
  $scope.changeRole = function(username,step){
    console.log("changing role: ",step,"for: ",username);
    var promise = $http.get("restapi/users/change_role/"+username+"/"+step);
    promise.then(function(data, status){
      $scope.update["success"] = true;
      $scope.update["fail"] = false;
      $scope.update["status_code"] = data.status;
      $scope.update["results"] = data.data.results;
      $window.location.reload();
    },function(data, status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = data.status;
    });
  };
  $scope.addMe = function(){
    var promise = $http.get("restapi/users/add_role");
    promise.then(function(data, status){
      $scope.update["success"] = true;
      $scope.update["fail"] = false;
      $scope.update["status_code"] = data.status;
      $window.location.reload();
    },function(data, status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = data.status;
    });
  };
};

// NEW for directive
var testApp = angular.module('testApp', ['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
